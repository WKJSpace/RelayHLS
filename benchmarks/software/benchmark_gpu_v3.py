"""Matched batch-one full-top BB72 latency; all private inputs remain remote."""
import hashlib
import json
import pathlib
import time
from types import SimpleNamespace

import numpy as np
import torch
import triton
import triton.language as tl
from fused_gpu import FusedDecoder


@triton.jit
def unpack_inputs(PackedP, PackedS, PackedC, P, S,
                  N: tl.constexpr, M: tl.constexpr, C: tl.constexpr,
                  BLOCK: tl.constexpr):
    j = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
    p = tl.load(PackedP + j // 2, j < N, 0).to(tl.int32)
    tl.store(P + j, (p >> ((j % 2) * 4)) & 15, j < N)
    s = tl.load(PackedS + j // 8, j < M, 0).to(tl.int32)
    c = tl.load(PackedC + j // 8, j < C, 0).to(tl.int32)
    value = ((s >> (j % 8)) & 1) ^ tl.where(j < C, (c >> (j % 8)) & 1, 0)
    tl.store(S + j, value, j < M)


@triton.jit
def output_parities(Best, Commit, Neighbors, Tail,
                    WIDTH: tl.constexpr):
    row = tl.program_id(0)
    d = tl.arange(0, WIDTH)
    v = tl.load(Neighbors + row * WIDTH + d)
    valid = v >= 0
    estimate = tl.load(Best + tl.maximum(v, 0), valid, 0).to(tl.int32)
    commit = tl.load(Commit + tl.maximum(v, 0), valid, 0).to(tl.int32)
    tl.store(Tail + row, tl.sum(estimate * commit, axis=0) & 1)


@triton.jit
def pack_outputs(Best, Tail, Control, Out, OutControl,
                 N: tl.constexpr, K: tl.constexpr, C: tl.constexpr,
                 EB: tl.constexpr, FB: tl.constexpr, CB: tl.constexpr,
                 BLOCK: tl.constexpr):
    byte = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
    b = tl.arange(0, 8)
    eindex = byte[:, None] * 8 + b[None, :]
    e = tl.load(Best + eindex, (byte[:, None] < EB) & (eindex < N), 0).to(tl.int32)
    framebyte = byte - EB
    findex = framebyte[:, None] * 8 + b[None, :]
    f = tl.load(Tail + findex,
                (framebyte[:, None] >= 0) & (framebyte[:, None] < FB) & (findex < K), 0).to(tl.int32)
    carrybyte = byte - EB - FB
    cindex = carrybyte[:, None] * 8 + b[None, :]
    c = tl.load(Tail + K + cindex,
                (carrybyte[:, None] >= 0) & (carrybyte[:, None] < CB) & (cindex < C), 0).to(tl.int32)
    values = tl.where(byte[:, None] < EB, e,
                      tl.where(byte[:, None] < EB + FB, f, c))
    packed = tl.sum(values << b[None, :], axis=1)
    tl.store(Out + byte, packed, byte < EB + FB + CB)
    if tl.program_id(0) == 0:
        s = tl.arange(0, 4)
        control_values = tl.load(Control + N + s, s < 3, 0).to(tl.int32)
        tl.store(OutControl + s, control_values, s < 3)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packed_bits(bits, length):
    out = np.zeros(length, dtype=np.uint8)
    for i, b in enumerate(bits):
        if int(b):
            out[i // 8] |= 1 << (i % 8)
    return out


class FullGPU:
    def __init__(self, data):
        self.n, self.m, self.k, self.c = (data[k] for k in ('n', 'm', 'k', 'carry_count'))
        e = data['e']
        assert (self.n, self.m, e, self.k, self.c) == (2240, 252, 7776, 12, 126)
        rows = np.full((self.m, max(map(len, data['row_edges']))), -1, dtype=np.int32)
        flat = []
        for i, r in enumerate(data['row_edges']):
            rows[i, :len(r)] = r
            flat.extend(r)
        assert sorted(flat) == list(range(e))
        faults = np.asarray(data['edge_fault'], dtype=np.int32)
        assert faults.shape == (e,) and int(faults.min()) >= 0 and int(faults.max()) < self.n
        degree = np.bincount(faults, minlength=self.n)
        model = SimpleNamespace(num_faults=self.n, num_detectors=self.m, num_edges=e,
                                row_edges=rows, edge_fault=faults, col_degree=degree,
                                policy=data['policy'])
        self.decoder = FusedDecoder(model, batch=1, cn_tile=32, vn_tile=64)
        self.eb, self.fb, self.cb = 280, 2, 16
        self.p = torch.zeros(self.n // 2, device='cuda', dtype=torch.uint8)
        self.s = torch.zeros(32, device='cuda', dtype=torch.uint8)
        self.carry = torch.zeros(16, device='cuda', dtype=torch.uint8)
        self.output = torch.zeros(self.eb+self.fb+self.cb, device='cuda', dtype=torch.uint8)
        self.control = torch.zeros(3, device='cuda', dtype=torch.int32)
        self.tail = torch.zeros(self.k+self.c, device='cuda', dtype=torch.uint8)
        commit = np.asarray(data['commit'], dtype=np.uint8)
        assert commit.shape == (self.n,) and np.isin(commit, [0, 1]).all()
        self.commit = torch.tensor(commit, device='cuda')
        assert len(data['tail_neighbors']) == self.k+self.c
        self.width = triton.next_power_of_2(max(map(len, data['tail_neighbors'])))
        neighbors = np.full((self.k+self.c, self.width), -1, dtype=np.int32)
        for i, row in enumerate(data['tail_neighbors']):
            assert all(0 <= x < self.n for x in row)
            neighbors[i, :len(row)] = row
        self.neighbors = torch.tensor(neighbors, device='cuda')
        self.host_output = torch.empty(self.output.shape, dtype=torch.uint8, pin_memory=True)
        self.host_control = torch.empty(3, dtype=torch.int32, pin_memory=True)
        stream = torch.cuda.Stream()
        stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(stream):
            self.run()
        torch.cuda.current_stream().wait_stream(stream)
        torch.cuda.synchronize()
        self.graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(self.graph):
            self.run()

    def run(self):
        unpack_inputs[(triton.cdiv(self.n, 256),)](
            self.p, self.s, self.carry, self.decoder.p, self.decoder.sy,
            self.n, self.m, self.c, 256)
        self.decoder._run()
        output_parities[(self.k+self.c,)](
            self.decoder.best, self.commit, self.neighbors, self.tail, self.width)
        pack_outputs[(triton.cdiv(self.eb+self.fb+self.cb, 64),)](
            self.decoder.best, self.tail, self.decoder.output, self.output, self.control,
            self.n, self.k, self.c, self.eb, self.fb, self.cb, 64)

    def stage(self, p, s, c):
        self.p.copy_(p, non_blocking=True)
        self.s.copy_(s, non_blocking=True)
        self.carry.copy_(c, non_blocking=True)

    def retrieve(self):
        self.host_output.copy_(self.output, non_blocking=True)
        self.host_control.copy_(self.control, non_blocking=True)

    def check(self, expected):
        it, candidates, conv = self.host_control.tolist()
        assert [it, candidates, conv] == expected[:3], 'GPU control mismatch'
        arr = self.host_output.numpy()
        for offset, width, text in ((0, self.n, expected[3]),
                                    (self.eb, self.k, expected[4]),
                                    (self.eb+self.fb, self.c, expected[5])):
            actual = ''.join(str(int((arr[offset+i//8] >> (i % 8)) & 1)) for i in range(width))
            assert actual == text, 'GPU packed output mismatch'


def main():
    import sys
    root = pathlib.Path(sys.argv[1])
    contract = json.loads((root/'data-contract.json').read_text())
    for name, digest in contract['files'].items():
        assert name in ('model.json', 'inputs.txt', 'native.log') and sha(root/name) == digest
    assert contract['input_sha256'] == '12575d3aa73a6e6bd3e05198166fa6545dc02934238e5c49f9cff9127c8dacc0'
    assert sha(pathlib.Path(__file__).with_name('fused_gpu.py')) == 'fef15bc46ba9921da7bc39b163086103e759a59b695329411a34d25b49b68ca7'
    assert torch.__version__.split('+')[0] == '2.13.0' and triton.__version__ == '3.7.1'
    assert np.__version__ == '2.3.3'
    assert torch.cuda.device_count() == 1 and torch.cuda.get_device_name(0) == 'NVIDIA L40S'
    data = json.loads((root/'model.json').read_text())
    tokens = list(map(int, (root/'inputs.txt').read_text().split()))
    assert tokens[0] == 32 and len(tokens) == 10305
    priors = tokens[1:2241]
    assert all(0 <= x <= 15 for x in priors)
    packed_p = np.asarray([priors[2*i] | (priors[2*i+1] << 4) for i in range(1120)], dtype=np.uint8)
    host_p = torch.empty(1120, dtype=torch.uint8, pin_memory=True)
    host_p.copy_(torch.from_numpy(packed_p))
    host_c = torch.zeros(16, dtype=torch.uint8, pin_memory=True)
    host_s = []
    for i in range(32):
        sy = tokens[2241+i*252:2241+(i+1)*252]
        assert all(x in (0, 1) for x in sy)
        s = torch.empty(32, dtype=torch.uint8, pin_memory=True)
        s.copy_(torch.from_numpy(packed_bits(sy, 32)))
        host_s.append(s)
    expected = []
    for line in (root/'native.log').read_text().splitlines():
        parts = line.split()
        assert len(parts) == 6 and list(map(len, parts[3:])) == [2240, 12, 126]
        expected.append([*map(int, parts[:3]), *parts[3:]])
    assert len(expected) == 32
    gpu = FullGPU(data)
    for i in range(32):
        gpu.stage(host_p, host_s[i], host_c)
        gpu.graph.replay()
        gpu.retrieve()
        torch.cuda.synchronize()
        gpu.check(expected[i])
    for i in range(8):
        gpu.stage(host_p, host_s[i], host_c)
        gpu.graph.replay()
    torch.cuda.synchronize()
    start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    device, host = [], []
    for trial in range(5):
        dtrial, htrial = [], []
        for i in range(32):
            gpu.stage(host_p, host_s[i], host_c)
            torch.cuda.synchronize()  # Inputs are resident before the device start event.
            start.record()
            gpu.graph.replay()
            end.record()
            end.synchronize()
            dtrial.append(start.elapsed_time(end)*1000.0)
            gpu.retrieve()
            torch.cuda.synchronize()
            gpu.check(expected[i])
        for i in range(32):
            before = time.perf_counter_ns()
            gpu.stage(host_p, host_s[i], host_c)
            gpu.graph.replay()
            gpu.retrieve()
            torch.cuda.synchronize()
            after = time.perf_counter_ns()
            htrial.append((after-before)/1000.0)
            gpu.check(expected[i])
        device.append(dtrial)
        host.append(htrial)
    report = dict(full_top_cases=32, field_comparisons=160, output_mismatches=0,
                  auxiliary_candidate_mismatches=0, batch_size=1,
                  device_trials_us=device, host_transfer_trials_us=host,
                  graph_sha256=contract['files']['model.json'], input_sha256=contract['input_sha256'],
                  torch_version=torch.__version__, triton_version=triton.__version__,
                  gpu_name=torch.cuda.get_device_name(0), cn_tile=32, vn_tile=64,
                  device_boundary='resident_packed_inputs_to_resident_five_outputs',
                  host_boundary='pinned_host_packed_inputs_H2D_graph_D2H_synchronize',
                  setup_and_validation_excluded=True)
    pathlib.Path(sys.argv[2]).write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
