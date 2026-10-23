"""Unseeded four-bit Relay-BP baseline with fused kernels and CUDA Graphs.

Graph compilation/capture and workspace allocation occur in the constructor.
decode() includes warm host input staging, H2D copies, replay, D2H correction and
control outputs, and synchronization. Optional posterior copying is for tests.
This baseline preserves the original zero estimate when no candidate is found.
"""
import numpy as np
import torch
import triton
import triton.language as tl


@triton.jit
def _init_faults(P, Post, Hard, Best, N: tl.constexpr, BLOCK: tl.constexpr):
    j = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
    b = tl.program_id(1)
    p = tl.load(P + b * N + j, j < N, 0).to(tl.int32)
    tl.store(Post + b * N + j, p, j < N)
    tl.store(Hard + b * N + j, 0, j < N)
    tl.store(Best + b * N + j, 0, j < N)


@triton.jit
def _init_edges(P, Faults, Q, E: tl.constexpr, N: tl.constexpr, BLOCK: tl.constexpr):
    e = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
    b = tl.program_id(1)
    f = tl.load(Faults + e, e < E, 0)
    p = tl.load(P + b * N + f, e < E, 0).to(tl.int32)
    tl.store(Q + b * E + e, p << 1, e < E)


@triton.jit
def _init_control(State):
    b = tl.program_id(0)
    s = tl.arange(0, 8)
    tl.store(State + b * 5 + s, tl.where(s == 2, 1048575, 0), s < 5)


@triton.jit
def _reset_leg(State):
    b = tl.program_id(0)
    tl.store(State + b * 5 + 3, 0)


@triton.jit
def _cn(Q, C, Rows, Sy, State, E: tl.constexpr, M: tl.constexpr,
        WIDTH: tl.constexpr, SHIFT: tl.constexpr, TILE: tl.constexpr):
    b = tl.program_id(1)
    active = (tl.load(State + b * 5 + 3) == 0) & (tl.load(State + b * 5 + 4) == 0)
    if active:
        r = tl.program_id(0) * TILE + tl.arange(0, TILE)
        d = tl.arange(0, WIDTH)
        edge = tl.load(Rows + r[:, None] * WIDTH + d[None, :], r[:, None] < M, -1)
        valid = edge >= 0
        packed = tl.load(Q + b * E + tl.maximum(edge, 0), valid, 0).to(tl.int32)
        sign = packed & 1
        mag = tl.where(valid, packed >> 1, 15)
        minimum = tl.min(mag, axis=1)
        repeated = tl.sum((mag == minimum[:, None]).to(tl.int32), axis=1) > 1
        second = tl.min(tl.where(mag > minimum[:, None], mag, 15), axis=1)
        second = tl.where(repeated, minimum, second)
        excluding = tl.where(mag == minimum[:, None], second[:, None], minimum[:, None])
        if SHIFT != 0:
            excluding = excluding - (excluding >> SHIFT)
        observed = tl.load(Sy + b * M + r, r < M, 0).to(tl.int32)
        parity = (tl.sum(tl.where(valid, sign, 0), axis=1) & 1) ^ observed
        outgoing = (excluding << 1) | (parity[:, None] ^ sign)
        tl.store(C + b * E + tl.maximum(edge, 0), outgoing, valid)


@triton.jit
def _vn(P, Post, Hard, Q, C, Columns, State, N: tl.constexpr, E: tl.constexpr,
        WIDTH: tl.constexpr, BETA: tl.constexpr, TILE: tl.constexpr):
    b = tl.program_id(1)
    active = (tl.load(State + b * 5 + 3) == 0) & (tl.load(State + b * 5 + 4) == 0)
    if active:
        j = tl.program_id(0) * TILE + tl.arange(0, TILE)
        d = tl.arange(0, WIDTH)
        edge = tl.load(Columns + j[:, None] * WIDTH + d[None, :], j[:, None] < N, -1)
        valid = edge >= 0
        used = tl.sum(valid.to(tl.int32), axis=1) > 0
        packed = tl.load(C + b * E + tl.maximum(edge, 0), valid, 0).to(tl.int32)
        mag = packed >> 1
        value = tl.where((packed & 1) != 0, -mag, mag)
        incoming = tl.sum(tl.where(valid, value, 0), axis=1)
        prior = tl.load(P + b * N + j, j < N, 0).to(tl.int32)
        previous = tl.load(Post + b * N + j, j < N, 0).to(tl.int32)
        # Both operands are signed int32, so each right shift is its own floor.
        bias = ((BETA * prior) >> 3) + (((8 - BETA) * previous) >> 3)
        bias = tl.minimum(tl.maximum(bias, -128), 127)
        bias = tl.where(tl.load(State + b * 5) == 0, prior, bias)
        posterior = tl.minimum(tl.maximum(bias + incoming, -128), 127)
        # The banked implementation skips unused columns: retain initialized
        # posterior there and emit a zero hard decision for their packed slot.
        tl.store(Post + b * N + j, posterior, (j < N) & used)
        tl.store(Hard + b * N + j, tl.where(used, posterior < 0, 0), j < N)
        extrinsic = tl.minimum(tl.maximum(posterior[:, None] - value, -128), 127)
        new_mag = tl.minimum(tl.abs(extrinsic), 15)
        outgoing = (new_mag << 1) | (extrinsic < 0).to(tl.int32)
        tl.store(Q + b * E + tl.maximum(edge, 0), outgoing, valid)


@triton.jit
def _parity(Hard, Faults, Rows, Sy, Mismatch, State, N: tl.constexpr,
            M: tl.constexpr, WIDTH: tl.constexpr, TILE: tl.constexpr):
    b = tl.program_id(1)
    active = (tl.load(State + b * 5 + 3) == 0) & (tl.load(State + b * 5 + 4) == 0)
    if active:
        r = tl.program_id(0) * TILE + tl.arange(0, TILE)
        d = tl.arange(0, WIDTH)
        edge = tl.load(Rows + r[:, None] * WIDTH + d[None, :], r[:, None] < M, -1)
        valid = edge >= 0
        fault = tl.load(Faults + tl.maximum(edge, 0), valid, 0)
        hard = tl.load(Hard + b * N + fault, valid, 0).to(tl.int32)
        parity = tl.sum(tl.where(valid, hard, 0), axis=1) & 1
        observed = tl.load(Sy + b * M + r, r < M, 0).to(tl.int32)
        tl.store(Mismatch + b * M + r, parity != observed, r < M)


@triton.jit
def _advance(State):
    b = tl.program_id(0)
    active = (tl.load(State + b * 5 + 3) == 0) & (tl.load(State + b * 5 + 4) == 0)
    if active:
        total = tl.load(State + b * 5)
        tl.store(State + b * 5, total + 1)


@triton.jit
def _check(P, Hard, Best, ActiveFaults, Mismatch, State, NextState,
           N: tl.constexpr, M: tl.constexpr, BLOCK: tl.constexpr):
    b = tl.program_id(0)
    # State is immutable during this multi-warp kernel. Otherwise a leading
    # warp can store the new cost before another warp reads the old cost,
    # suppressing only that warp's part of the candidate correction.
    total = tl.load(State + b * 5)
    candidates = tl.load(State + b * 5 + 1)
    best_cost = tl.load(State + b * 5 + 2)
    leg_done = tl.load(State + b * 5 + 3)
    finished = tl.load(State + b * 5 + 4)
    active = (leg_done == 0) & (finished == 0)
    if active:
        total += 1
        j = tl.arange(0, BLOCK)
        mismatch = tl.load(Mismatch + b * M + j, j < M, 0).to(tl.int32)
        converged = tl.sum(mismatch, axis=0) == 0
        if converged:
            hard = tl.load(Hard + b * N + j, j < N, 0).to(tl.int32)
            prior = tl.load(P + b * N + j, j < N, 0).to(tl.int32)
            used = tl.load(ActiveFaults + j, j < N, 0).to(tl.int32)
            cost = tl.sum(hard * prior * used, axis=0) & 1048575
            if cost < best_cost:
                tl.store(Best + b * N + j, hard, j < N)
                best_cost = cost
            candidates += 1
            leg_done = 1
            finished = (candidates >= 2).to(tl.int32)
    s = tl.arange(0, 8)
    values = tl.where(s == 0, total, tl.where(s == 1, candidates,
             tl.where(s == 2, best_cost, tl.where(s == 3, leg_done, finished))))
    tl.store(NextState + b * 5 + s, values, s < 5)


@triton.jit
def _commit_control(NextState, State):
    b = tl.program_id(0)
    s = tl.arange(0, 8)
    values = tl.load(NextState + b * 5 + s, s < 5, 0)
    tl.store(State + b * 5 + s, values, s < 5)


@triton.jit
def _publish(Best, State, Output, N: tl.constexpr, BLOCK: tl.constexpr):
    b = tl.program_id(1)
    j = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
    best = tl.load(Best + b * N + j, j < N, 0)
    tl.store(Output + b * (N + 3) + j, best, j < N)
    if tl.program_id(0) == 0:
        total = tl.load(State + b * 5)
        candidates = tl.load(State + b * 5 + 1)
        tl.store(Output + b * (N + 3) + N, total)
        tl.store(Output + b * (N + 3) + N + 1, candidates)
        tl.store(Output + b * (N + 3) + N + 2, candidates > 0)


class FusedDecoder:
    def __init__(self, model, batch=1, cn_tile=4, vn_tile=8):
        expected = dict(WEIGHT_BITS=20, LEG_BETA=[7, 5, 3, 1], MEM_SHIFT=3,
                        MAX_LEGS=4, MAX_ITERS_PER_LEG=10, GLOBAL_MAX_ITERS=40,
                        MAX_SOLUTIONS=2, ALPHA_SHIFT_MAX=4,
                        CONVERGENCE_CHECK_INTERVAL=2)
        if any(model.policy[k] != v for k, v in expected.items()):
            raise ValueError("This baseline supports exactly the evaluated four-bit policy")
        if batch < 1 or not torch.cuda.is_available():
            raise ValueError("A positive batch size and CUDA device are required")
        self.n, self.m, self.e = model.num_faults, model.num_detectors, model.num_edges
        self.batch, self.cn_tile, self.vn_tile = batch, cn_tile, vn_tile
        self.row_width = triton.next_power_of_2(model.row_edges.shape[1])
        self.col_width = triton.next_power_of_2(max(1, int(model.col_degree.max())))
        rows = np.full((self.m, self.row_width), -1, dtype=np.int32)
        rows[:, :model.row_edges.shape[1]] = model.row_edges
        columns = np.full((self.n, self.col_width), -1, dtype=np.int32)
        used = np.zeros(self.n, dtype=np.int32)
        for edge, fault in enumerate(model.edge_fault):
            columns[fault, used[fault]] = edge
            used[fault] += 1
        self.rows = torch.tensor(rows, device="cuda", dtype=torch.int32)
        self.columns = torch.tensor(columns, device="cuda", dtype=torch.int32)
        self.faults = torch.tensor(model.edge_fault, device="cuda", dtype=torch.int32)
        self.active_faults = torch.tensor(model.col_degree > 0, device="cuda", dtype=torch.uint8)
        def alloc(shape, dtype):
            return torch.zeros(shape, device="cuda", dtype=dtype)
        self.p = alloc((batch, self.n), torch.uint8)
        self.sy = alloc((batch, self.m), torch.uint8)
        self.post = alloc((batch, self.n), torch.int16)
        self.hard = alloc((batch, self.n), torch.uint8)
        self.best = alloc((batch, self.n), torch.uint8)
        self.q, self.c = alloc((batch, self.e), torch.uint8), alloc((batch, self.e), torch.uint8)
        self.mismatch = alloc((batch, self.m), torch.uint8)
        self.state = alloc((batch, 5), torch.int32)
        self.next_state = alloc((batch, 5), torch.int32)
        self.output = alloc((batch, self.n + 3), torch.uint8)
        self.host_p = torch.empty((batch, self.n), dtype=torch.uint8, pin_memory=True)
        self.host_sy = torch.empty((batch, self.m), dtype=torch.uint8, pin_memory=True)
        self.host_output = torch.empty((batch, self.n + 3), dtype=torch.uint8, pin_memory=True)
        self.host_p_np, self.host_sy_np = self.host_p.numpy(), self.host_sy.numpy()
        self.host_output_np = self.host_output.numpy()
        # Warm compilation on a side stream before capture, as required by CUDA.
        stream = torch.cuda.Stream()
        stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(stream):
            self._run()
        torch.cuda.current_stream().wait_stream(stream)
        torch.cuda.synchronize()
        self.graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(self.graph):
            self._run()

    def _run(self):
        n, m, e, batch = self.n, self.m, self.e, self.batch
        _init_faults[(triton.cdiv(n, 256), batch)](self.p, self.post, self.hard, self.best, n, 256)
        _init_edges[(triton.cdiv(e, 256), batch)](self.p, self.faults, self.q, e, n, 256)
        _init_control[(batch,)](self.state)
        for leg, beta in enumerate([7, 5, 3, 1]):
            if leg:
                _reset_leg[(batch,)](self.state)
            for update in range(10):
                _cn[(triton.cdiv(m, self.cn_tile), batch)](
                    self.q, self.c, self.rows, self.sy, self.state,
                    e, m, self.row_width, min(update, 4), self.cn_tile)
                _vn[(triton.cdiv(n, self.vn_tile), batch)](
                    self.p, self.post, self.hard, self.q, self.c, self.columns, self.state,
                    n, e, self.col_width, beta, self.vn_tile)
                if (update + 1) % 2 == 0:
                    _parity[(triton.cdiv(m, self.cn_tile), batch)](
                        self.hard, self.faults, self.rows, self.sy, self.mismatch, self.state,
                        n, m, self.row_width, self.cn_tile)
                    _check[(batch,)](self.p, self.hard, self.best, self.active_faults,
                                     self.mismatch, self.state, self.next_state, n, m,
                                     triton.next_power_of_2(max(n, m)), num_warps=8)
                    _commit_control[(batch,)](self.next_state, self.state, num_warps=1)
                else:
                    _advance[(batch,)](self.state)
        _publish[(triton.cdiv(n, 256), batch)](self.best, self.state, self.output, n, 256)

    def decode(self, syndrome, priors, posterior=False):
        sy, p = np.asarray(syndrome), np.asarray(priors)
        if sy.shape != (self.batch, self.m) or np.any((sy != 0) & (sy != 1)):
            raise ValueError("Binary syndrome shape mismatch")
        if p.shape == (self.n,):
            p = np.broadcast_to(p, (self.batch, self.n))
        if p.shape != (self.batch, self.n) or np.any((p < 0) | (p > 15)) or np.any(p != np.floor(p)):
            raise ValueError("Priors must be unsigned four-bit integers")
        np.copyto(self.host_sy_np, sy, casting="unsafe")
        np.copyto(self.host_p_np, p, casting="unsafe")
        self.sy.copy_(self.host_sy, non_blocking=True)
        self.p.copy_(self.host_p, non_blocking=True)
        self.graph.replay()
        self.host_output.copy_(self.output, non_blocking=True)
        torch.cuda.current_stream().synchronize()
        out = self.host_output_np.copy()
        result = dict(estimate=out[:, :self.n].astype(bool), iterations=out[:, self.n],
                      solutions=out[:, self.n+1], converged=out[:, self.n+2].astype(bool))
        if posterior:
            result["posterior"] = self.post.cpu().numpy().copy()
        return result
