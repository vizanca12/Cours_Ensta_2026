#!/usr/bin/env python3
"""Minimal benchmark harness.

Runs ant_simu.exe (OO or SoA) and ant_simu_mpi.exe multiple times and reports
mean/std of per-iteration timings.

This matches the course guidance: multiple runs, report average and standard
deviation, keep runs reproducible.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import statistics
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class RunResult:
    per_iter: Dict[str, float]
    raw: str


AVG_ITER_SECTION_RE = re.compile(r"^==== Timings \(avg/iter\) ====\s*$", re.M)
MPI_AVG_ITER_SECTION_RE = re.compile(r"^==== Timings \(avg rank, per-iter\) ====\s*$", re.M)


def parse_kv_section(text: str, start_re: re.Pattern) -> Dict[str, float]:
    m = start_re.search(text)
    if not m:
        raise ValueError("Could not find avg/iter section")
    start = m.end()
    tail = text[start:]

    out: Dict[str, float] = {}
    for line in tail.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("===="):
            break
        m2 = re.match(r"^([^:]+):\s*([0-9.eE+-]+)\s*s$", line)
        if m2:
            out[m2.group(1).strip()] = float(m2.group(2))
    if not out:
        raise ValueError("avg/iter section parsed empty")
    return out


def run_cmd(cmd: List[str], env: Dict[str, str] | None = None) -> str:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True, check=True)
    return proc.stdout


def summarize(results: List[RunResult]) -> Tuple[Dict[str, float], Dict[str, float]]:
    keys = sorted({k for r in results for k in r.per_iter.keys()})
    means: Dict[str, float] = {}
    stds: Dict[str, float] = {}
    for k in keys:
        vals = [r.per_iter[k] for r in results if k in r.per_iter]
        means[k] = statistics.mean(vals)
        stds[k] = statistics.pstdev(vals) if len(vals) > 1 else 0.0
    return means, stds


def print_table(means: Dict[str, float], stds: Dict[str, float], title: str) -> None:
    print(f"\n== {title} ==")
    for k in sorted(means.keys()):
        print(f"{k:20s}  mean={means[k]:.6e} s  std={stds[k]:.6e} s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=500)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--ants", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--threads", type=int, nargs="*", default=[1, 2, 4, 8])
    ap.add_argument("--soa", action="store_true", help="Benchmark SoA mode")
    ap.add_argument("--mpi", action="store_true", help="Benchmark MPI (approach 1)")
    ap.add_argument("--ranks", type=int, nargs="*", default=[1, 2, 4])
    ap.add_argument("--mpi-ants", type=int, default=20000)
    ap.add_argument("--omp-threads", type=int, default=1)
    args = ap.parse_args()

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    ant_simu = os.path.join(root, "src", "ant_simu.exe")
    ant_mpi = os.path.join(root, "src", "ant_simu_mpi.exe")

    if args.mpi:
        for p in args.ranks:
            results: List[RunResult] = []
            for _ in range(args.runs):
                cmd = ["mpirun", "-np", str(p), ant_mpi, "--steps", str(args.steps), "--ants", str(args.mpi_ants), "--omp-threads", str(args.omp_threads)]
                out = run_cmd(cmd)
                per_iter = parse_kv_section(out, MPI_AVG_ITER_SECTION_RE)
                results.append(RunResult(per_iter=per_iter, raw=out))
            means, stds = summarize(results)
            print_table(means, stds, f"MPI ranks={p} (avg rank per-iter) steps={args.steps} runs={args.runs}")
        return

    # OpenMP / single-process
    for t in args.threads:
        results = []
        env = dict(os.environ)
        env["OMP_NUM_THREADS"] = str(t)
        for _ in range(args.runs):
            cmd = [ant_simu, "--no-gui", "--steps", str(args.steps), "--ants", str(args.ants), "--seed", str(args.seed)]
            if args.soa:
                cmd.insert(1, "--vectorized")
            out = run_cmd(cmd, env=env)
            per_iter = parse_kv_section(out, AVG_ITER_SECTION_RE)
            results.append(RunResult(per_iter=per_iter, raw=out))
        means, stds = summarize(results)
        mode = "SoA" if args.soa else "OO"
        print_table(means, stds, f"{mode} OMP_NUM_THREADS={t} steps={args.steps} runs={args.runs}")


if __name__ == "__main__":
    main()
