#!/usr/bin/env python3
"""Compile and run the scalar/controller regressions using installed Vitis headers."""
import argparse
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def window_fixture(destination):
    """A tiny algebraic fixture with nonzero logical/carry outputs, not a circuit benchmark."""
    template = ROOT / "variants/RelayBP_pack64_c16_v32"
    shutil.copytree(template / "src", destination / "src")
    shutil.copytree(template / "testbench", destination / "testbench")
    path = template / "tools/generate_real_circuit_constants.py"
    spec = importlib.util.spec_from_file_location("native_real", path)
    real = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real)
    config = dict(real.fake.DEFAULT_CONFIG)
    config.update(WINDOW_W=2, M_PER_CYCLE=2, NUM_FAULTS=5, LOGICAL_QUBITS=1,
                  CNU_PARALLEL=2, VNU_PARALLEL=2, CONVERGENCE_PARALLEL=2,
                  PACK_BITS=4, PACKED_BANK_FACTOR=4, PRIOR_PACK_FACTOR=4,
                  PRIOR_BANK_FACTOR=4, EDGE_BANK_FACTOR=4)
    graph = real.CircuitGraph(4, 5, [(0, 0), (1, 0), (2, 2), (3, 3)], [(0, 2)], [])
    matrix = real.build_real_h(graph, config)
    header = real.render_real_constants(config, graph, matrix)
    header, count = re.subn(r"constexpr int COMMIT_MASK\[NUM_FAULTS\]\s*=\s*\{[^}]*\};",
                           "constexpr int COMMIT_MASK[NUM_FAULTS] = {1, 1, 1, 1, 1};", header)
    assert count == 1
    (destination / "src/constants.h").write_text(header)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include", required=True, help="Vitis include directory containing ap_int.h")
    parser.add_argument("--gmp", default="-lgmp", help="GMP linker flag or full library path")
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    if not (Path(args.include) / "ap_int.h").is_file():
        parser.error("--include must contain ap_int.h")
    with tempfile.TemporaryDirectory(prefix="relayhls-native-") as temporary:
        variants = sorted((ROOT / "variants").glob("RelayBP_pack64_*"))
        fixture = window_fixture(Path(temporary) / "window-fixture")
        for variant in variants + [fixture]:
            executable = Path(temporary) / (variant.name + ".test")
            command = [args.cxx, "-O2", "-std=c++14", "-Wno-unknown-pragmas",
                       "-I" + args.include, "-I" + str(variant), "-I" + str(variant / "src"),
                       str(ROOT / "tests/decoder_regression.cpp"),
                       str(variant / "src/decoder_top.cpp"), args.gmp, "-o", str(executable)]
            if variant == fixture:
                command.insert(1, "-DRELAYHLS_WINDOW_FIXTURE")
            subprocess.run(command, check=True)
            print(variant.name, flush=True)
            subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    main()
