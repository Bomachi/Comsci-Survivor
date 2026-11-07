"""Benchmark crowd separation: naive O(n^2) vs spatial hash.

Run:  python benchmarks/collision_benchmark.py
Writes benchmarks/results.csv and, if matplotlib is installed, benchmarks/collision_benchmark.png
"""
import copy
import csv
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spatial import separate  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SIZES = [50, 100, 200, 400, 800, 1200, 1600, 2000]
REPEATS = 5
DENSITY = 2500  # world area per enemy (px^2): same crowd density at every size


class Body:
    def __init__(self, x, y, r):
        self.x, self.y, self.radius = x, y, r


def make_crowd(n, seed):
    rng = random.Random(seed)
    side = (n * DENSITY) ** 0.5
    return [Body(rng.uniform(0, side), rng.uniform(0, side), rng.choice([14, 16, 21])) for _ in range(n)]


def measure(n, mode):
    times, checks = [], 0
    for rep in range(REPEATS):
        crowd = make_crowd(n, rep)
        start = time.perf_counter()
        stats = separate(crowd, mode)
        times.append((time.perf_counter() - start) * 1000)
        checks = stats.checks
    return statistics.median(times), checks


def main():
    rows = []
    print(f"{'enemies':>8} {'naive ms':>10} {'hash ms':>9} {'speedup':>8} {'naive checks':>13} {'hash checks':>12}")
    for n in SIZES:
        naive_ms, naive_checks = measure(n, "naive")
        hash_ms, hash_checks = measure(n, "hash")
        rows.append((n, naive_ms, hash_ms, naive_checks, hash_checks))
        print(f"{n:>8} {naive_ms:>10.2f} {hash_ms:>9.2f} {naive_ms / hash_ms:>7.1f}x {naive_checks:>13,} {hash_checks:>12,}")
    with open(os.path.join(HERE, "results.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["enemies", "naive_ms", "hash_ms", "naive_checks", "hash_checks"])
        writer.writerows(rows)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: skipped the chart (pip install matplotlib)")
        return
    n = [r[0] for r in rows]
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.2))
    left.plot(n, [r[1] for r in rows], "o-", color="#d9534f", label="Naive O(n²)")
    left.plot(n, [r[2] for r in rows], "o-", color="#2a9d8f", label="Spatial hash ~O(n)")
    left.axhline(16.7, color="gray", linestyle="--", linewidth=1)
    left.text(n[0], 17.5, "1 frame at 60 FPS (16.7 ms)", color="gray", fontsize=9)
    left.set(title="Separation time per frame", xlabel="Enemies on screen", ylabel="ms (median)")
    left.legend()
    right.plot(n, [r[3] for r in rows], "o-", color="#d9534f", label="Naive")
    right.plot(n, [r[4] for r in rows], "o-", color="#2a9d8f", label="Spatial hash")
    right.set_yscale("log")
    right.set(title="Distance checks per frame (log scale)", xlabel="Enemies on screen", ylabel="pair checks")
    right.legend()
    fig.tight_layout()
    out = os.path.join(HERE, "collision_benchmark.png")
    fig.savefig(out, dpi=150)
    print("chart:", out)


if __name__ == "__main__":
    main()
