#!/usr/bin/env python3
"""Explicit user-invoked native reproduction of one released 32-case fixture."""
import argparse
import os
from pathlib import Path
import subprocess
from verify_release import ROOT, verify_fixture

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workload',choices=['bb72','bb144'])
    parser.add_argument('point',choices=['c1v2','c1v4','c1v8','c2v2','c2v4','c2v8','c4v2','c4v4','c4v8'])
    parser.add_argument('--include',required=True,type=Path,help='Directory containing the installed AMD ap_int.h')
    parser.add_argument('--cxx',default=os.environ.get('CXX','g++'))
    parser.add_argument('--gmp',help='Optional full path to libgmp; otherwise -lgmp is used')
    args=parser.parse_args()
    folder=ROOT/'benchmarks'/args.workload/args.point
    if not folder.is_dir():parser.error('This configuration is outside the release selection')
    verify_fixture(folder)
    include=args.include.resolve()
    if not (include/'ap_int.h').is_file():parser.error('--include must contain ap_int.h')
    build=ROOT/'build'/('native-'+args.workload+'-'+args.point)
    build.mkdir(parents=True,exist_ok=False)
    binary=build/'decoder-test'
    command=[args.cxx,'-std=c++17','-O1','-Wno-unknown-pragmas','-I'+str(include),'-I'+str(folder/'src'),str(folder/'src/decoder_top.cpp'),str(folder/'testbench/native_oracle.cpp'),args.gmp or '-lgmp','-o',str(binary)]
    subprocess.run(command,check=True,timeout=900)
    with (folder/'inputs.txt').open('rb') as inputs,(build/'outputs.txt').open('wb') as output:
        subprocess.run([str(binary)],stdin=inputs,stdout=output,check=True,timeout=600,cwd=build)
    if (build/'outputs.txt').read_bytes()!=(folder/'golden.txt').read_bytes():
        raise RuntimeError('Native output does not match all 32 golden cases')
    print('All 32 native results match the frozen golden outputs.')

if __name__=='__main__':main()
