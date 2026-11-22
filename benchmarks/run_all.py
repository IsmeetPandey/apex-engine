#!/usr/bin/env python3
"""
ApexEngine Unified Benchmark Runner.
Executes Phase 1 (Context Memory Compaction), Phase 2 (Head-to-Head Comparative Simulation),
and Phase 3 (Variable Amnesia & Invariant State Binding).

Usage:
    python benchmarks/run_all.py
"""

import os
import sys
import subprocess


def run_all():
    benchmarks_dir = os.path.dirname(os.path.abspath(__file__))
    memory_bench = os.path.join(benchmarks_dir, "benchmark_memory.py")
    h2h_bench = os.path.join(benchmarks_dir, "benchmark_head_to_head.py")
    amnesia_bench = os.path.join(benchmarks_dir, "benchmark_amnesia.py")

    print("\n" + "=" * 80)
    print("           APEXENGINE SUITE: RUNNING ALL EMPIRICAL BENCHMARKS")
    print("=" * 80 + "\n")

    print(">>> [Phase 1/3] Running Context Token Compaction Benchmark...")
    subprocess.run([sys.executable, memory_bench], check=True)

    print("\n>>> [Phase 2/3] Running Head-to-Head Agentic Simulation Benchmark...")
    subprocess.run([sys.executable, h2h_bench], check=True)

    print("\n>>> [Phase 3/3] Running Variable Amnesia & Invariant Binding Benchmark...")
    subprocess.run([sys.executable, amnesia_bench], check=True)

    print("\n" + "=" * 80)
    print("   ALL BENCHMARKS COMPLETED SUCCESSFULLY — 100% REPRODUCIBLE (EXIT CODE 0)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_all()
