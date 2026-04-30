"""Simulates Python-pure vs PyO3 performance comparisons for CPU-bound operations.

All measurements are taken in Python-only implementations.
PyO3/Rust times are extrapolated from published speedup factors documented in
the PyO3 guide and community benchmarks:
  https://pyo3.rs/v0.21.0/performance

Categories and expected speedup ranges:
  - String processing    : 8–15x
  - Numeric computation  : 20–50x
  - List sorting         : 5–10x
  - Memory-intensive ops : 10–30x
"""

from __future__ import annotations

import math
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class BenchResult:
    """Timing result for one benchmark run."""

    name: str
    category: str
    python_ms: float
    speedup_low: float  # conservative Rust/PyO3 multiplier
    speedup_high: float  # optimistic Rust/PyO3 multiplier
    iterations: int = 1
    notes: str = ""

    @property
    def rust_low_ms(self) -> float:
        """Lower-bound Rust time (fewer ms = faster)."""
        return self.python_ms / self.speedup_high

    @property
    def rust_high_ms(self) -> float:
        """Upper-bound Rust time (more ms = slower)."""
        return self.python_ms / self.speedup_low

    @property
    def speedup_mid(self) -> float:
        return (self.speedup_low + self.speedup_high) / 2


@dataclass
class BenchSuite:
    """Collection of benchmark results for one category."""

    category: str
    results: list[BenchResult] = field(default_factory=list)

    def add(self, result: BenchResult) -> None:
        self.results.append(result)

    def mean_python_ms(self) -> float:
        if not self.results:
            return 0.0
        return statistics.mean(r.python_ms for r in self.results)

    def mean_speedup(self) -> float:
        if not self.results:
            return 0.0
        return statistics.mean(r.speedup_mid for r in self.results)


# ---------------------------------------------------------------------------
# Pure-Python implementations (measured)
# ---------------------------------------------------------------------------


def py_count_vowels(text: str) -> int:
    """Count ASCII vowels in a string."""
    return sum(1 for c in text if c in "aeiouAEIOU")


def py_reverse_words(text: str) -> str:
    """Reverse each word in a space-delimited string."""
    return " ".join(w[::-1] for w in text.split())


def py_word_frequency(text: str) -> dict[str, int]:
    """Build a word-frequency map."""
    freq: dict[str, int] = {}
    for w in text.lower().split():
        freq[w] = freq.get(w, 0) + 1
    return freq


def py_sum_squares(n: int) -> float:
    """Sum of squares 1..n."""
    return sum(float(i * i) for i in range(1, n + 1))


def py_is_prime(n: int) -> bool:
    """Trial-division primality test."""
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(math.isqrt(n)) + 1, 2):
        if n % i == 0:
            return False
    return True


def py_count_primes(limit: int) -> int:
    """Count primes up to limit using trial division."""
    return sum(1 for n in range(2, limit + 1) if py_is_prime(n))


def py_sort_strings(strings: list[str]) -> list[str]:
    """Sort a list of strings lexicographically."""
    return sorted(strings)


def py_sort_tuples(pairs: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Sort list of (int, str) pairs by int key."""
    return sorted(pairs, key=lambda x: x[0])


def py_matrix_multiply(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    """Naive O(n^3) matrix multiply."""
    n = len(a)
    result = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for k in range(n):
            a_ik = a[i][k]
            for j in range(n):
                result[i][j] += a_ik * b[k][j]
    return result


def py_flatten_nested(data: list[Any], depth: int = 2) -> list[Any]:
    """Flatten a nested list up to the given depth."""
    if depth == 0:
        return data  # type: ignore[return-value]
    flat: list[Any] = []
    for item in data:
        if isinstance(item, list):
            flat.extend(py_flatten_nested(item, depth - 1))
        else:
            flat.append(item)
    return flat


# ---------------------------------------------------------------------------
# Timing harness
# ---------------------------------------------------------------------------


def _time_ms(fn: Callable[[], Any], warmup: int = 1, runs: int = 5) -> float:
    """Return median wall-clock milliseconds for ``fn()``."""
    for _ in range(warmup):
        fn()
    samples: list[float] = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.median(samples)


# ---------------------------------------------------------------------------
# Build benchmark suites
# ---------------------------------------------------------------------------


def bench_string_processing() -> BenchSuite:
    """String manipulation benchmarks."""
    suite = BenchSuite(category="String processing")
    corpus = " ".join(["hello", "world", "pyo3", "rust", "python"] * 2000)
    long_text = corpus * 4  # ~240 kB string

    suite.add(
        BenchResult(
            name="count_vowels",
            category="String processing",
            python_ms=_time_ms(lambda: py_count_vowels(long_text)),
            speedup_low=8.0,
            speedup_high=15.0,
            notes="SIMD-friendly loop; Rust can use memchr or manual SIMD.",
        )
    )
    suite.add(
        BenchResult(
            name="reverse_words",
            category="String processing",
            python_ms=_time_ms(lambda: py_reverse_words(corpus)),
            speedup_low=6.0,
            speedup_high=12.0,
            notes="Allocation-heavy in Python; Rust can reuse a single Vec<u8>.",
        )
    )
    suite.add(
        BenchResult(
            name="word_frequency",
            category="String processing",
            python_ms=_time_ms(lambda: py_word_frequency(corpus)),
            speedup_low=5.0,
            speedup_high=10.0,
            notes="HashMap<&str, u32> in Rust; avoids Python dict boxing overhead.",
        )
    )
    return suite


def bench_numeric_computation() -> BenchSuite:
    """CPU-bound numeric benchmarks."""
    suite = BenchSuite(category="Numeric computation")

    suite.add(
        BenchResult(
            name="sum_squares_1M",
            category="Numeric computation",
            python_ms=_time_ms(lambda: py_sum_squares(1_000_000)),
            speedup_low=20.0,
            speedup_high=50.0,
            notes="Pure float loop; Rust auto-vectorises with -O3.",
        )
    )
    suite.add(
        BenchResult(
            name="count_primes_10k",
            category="Numeric computation",
            python_ms=_time_ms(lambda: py_count_primes(10_000)),
            speedup_low=25.0,
            speedup_high=50.0,
            notes="Integer trial division; Rust integers are register-width.",
        )
    )
    return suite


def bench_list_sorting() -> BenchSuite:
    """Sorting benchmarks."""
    import random

    rng = random.Random(42)

    suite = BenchSuite(category="List sorting")

    strings = [f"item_{rng.randint(0, 100_000):08d}" for _ in range(50_000)]
    suite.add(
        BenchResult(
            name="sort_50k_strings",
            category="List sorting",
            python_ms=_time_ms(lambda: py_sort_strings(strings[:])),
            speedup_low=5.0,
            speedup_high=10.0,
            notes="Timsort vs Rust sort; Python GC overhead per comparison.",
        )
    )

    pairs = [(rng.randint(0, 10_000), f"val_{i}") for i in range(30_000)]
    suite.add(
        BenchResult(
            name="sort_30k_tuples_by_key",
            category="List sorting",
            python_ms=_time_ms(lambda: py_sort_tuples(pairs[:])),
            speedup_low=4.0,
            speedup_high=8.0,
            notes="Key extraction callback overhead eliminated in Rust.",
        )
    )
    return suite


def bench_memory_intensive() -> BenchSuite:
    """Memory-allocation-heavy benchmarks."""
    suite = BenchSuite(category="Memory-intensive")

    size = 80
    a = [[float(i * size + j) for j in range(size)] for i in range(size)]
    b = [[float(i + j) for j in range(size)] for i in range(size)]

    suite.add(
        BenchResult(
            name=f"matrix_multiply_{size}x{size}",
            category="Memory-intensive",
            python_ms=_time_ms(lambda: py_matrix_multiply(a, b), warmup=0, runs=3),
            speedup_low=10.0,
            speedup_high=30.0,
            notes="Cache-friendly inner loop; Rust LLVM can autovectorise.",
        )
    )

    nested = [[list(range(20)) for _ in range(20)] for _ in range(50)]
    suite.add(
        BenchResult(
            name="flatten_nested_50x20x20",
            category="Memory-intensive",
            python_ms=_time_ms(lambda: py_flatten_nested(nested)),
            speedup_low=8.0,
            speedup_high=20.0,
            notes="Many small allocations in Python; Rust pre-allocates with_capacity.",
        )
    )
    return suite


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------

_COL_W = (30, 12, 14, 14, 12)


def _header() -> str:
    cols = ("Benchmark", "Python ms", "Rust low ms", "Rust high ms", "Speedup")
    sep = "  ".join("-" * w for w in _COL_W)
    row = "  ".join(f"{c:<{w}}" for c, w in zip(cols, _COL_W))
    return row + "\n" + sep


def _row(r: BenchResult) -> str:
    return "  ".join(
        [
            f"{r.name:<{_COL_W[0]}}",
            f"{r.python_ms:<{_COL_W[1]}.2f}",
            f"{r.rust_low_ms:<{_COL_W[2]}.2f}",
            f"{r.rust_high_ms:<{_COL_W[3]}.2f}",
            f"{r.speedup_low:.0f}–{r.speedup_high:.0f}x",
        ]
    )


def print_suite(suite: BenchSuite) -> None:
    """Print a formatted table for one benchmark suite."""
    print(f"\n{'=' * 72}")
    print(f"Category: {suite.category}")
    print(f"  Mean Python time : {suite.mean_python_ms():.2f} ms")
    print(f"  Mean speedup (mid): {suite.mean_speedup():.1f}x")
    print(f"{'=' * 72}")
    print(_header())
    for r in suite.results:
        print(_row(r))
        if r.notes:
            print(f"  {'':>{_COL_W[0]}}  ↳ {r.notes}")


def print_summary(suites: list[BenchSuite]) -> None:
    """Print a one-line-per-category summary."""
    print("\n" + "=" * 72)
    print("Summary: Python-pure vs extrapolated PyO3/Rust speedups")
    print("=" * 72)
    print(f"  {'Category':<28} {'Mean Python ms':>15} {'Speedup range':>15}")
    print(f"  {'-' * 28} {'-' * 15} {'-' * 15}")
    all_results: list[BenchResult] = []
    for s in suites:
        all_results.extend(s.results)
        low = min(r.speedup_low for r in s.results)
        high = max(r.speedup_high for r in s.results)
        print(f"  {s.category:<28} {s.mean_python_ms():>15.2f} {low:.0f}–{high:.0f}x")

    overall_speedup = statistics.mean(r.speedup_mid for r in all_results)
    overall_py_ms = statistics.mean(r.python_ms for r in all_results)
    print(
        f"\n  {'Overall average':<28} {overall_py_ms:>15.2f} {overall_speedup:>13.1f}x"
    )
    print()
    print("  Note: Rust times are extrapolated, NOT measured.")
    print("        Actual speedup depends on PyO3 boundary overhead, data size,")
    print("        CPU architecture, and Rust optimisation flags (-C opt-level=3).")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run all benchmark suites and print reports."""
    print("PyO3 Performance Comparison")
    print("Measuring Python-pure implementations; extrapolating Rust/PyO3 times.")
    print()

    suites = [
        bench_string_processing(),
        bench_numeric_computation(),
        bench_list_sorting(),
        bench_memory_intensive(),
    ]

    for suite in suites:
        print_suite(suite)

    print_summary(suites)


if __name__ == "__main__":
    main()
