"""GIL acquisition patterns for PyO3."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator


class GILAcquireMode(str, Enum):
    """Strategies for GIL acquisition in PyO3."""

    PYTHON = "Python::with_gil"
    ALLOW_THREADS = "allow_threads"
    ACQUIRE = "Python::acquire_gil"
    SUBINTERPRETER = "subinterpreter"

    def releases_gil(self) -> bool:
        return self == GILAcquireMode.ALLOW_THREADS


@dataclass
class GILGuard:
    """Represents a GIL guard token."""

    acquired_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    mode: GILAcquireMode = GILAcquireMode.PYTHON
    released: bool = False

    def release(self) -> None:
        self.released = True

    def hold_duration_ms(self) -> float:
        end = datetime.now(UTC) if not self.released else self.acquired_at
        return (end - self.acquired_at).total_seconds() * 1000

    def is_active(self) -> bool:
        return not self.released


@dataclass
class GILStats:
    """Statistics for GIL acquisition patterns."""

    total_acquisitions: int = 0
    total_releases: int = 0
    total_hold_time_ms: float = 0.0
    max_hold_time_ms: float = 0.0
    allow_threads_calls: int = 0
    contention_events: int = 0

    def record_acquisition(self, hold_ms: float) -> None:
        self.total_acquisitions += 1
        self.total_hold_time_ms += hold_ms
        self.max_hold_time_ms = max(self.max_hold_time_ms, hold_ms)

    def record_release(self) -> None:
        self.total_releases += 1

    def record_allow_threads(self) -> None:
        self.allow_threads_calls += 1

    def mean_hold_time_ms(self) -> float:
        if self.total_acquisitions == 0:
            return 0.0
        return self.total_hold_time_ms / self.total_acquisitions

    def is_contended(self, threshold_ms: float = 10.0) -> bool:
        return self.mean_hold_time_ms() > threshold_ms or self.contention_events > 0


class GILTracker:
    """Tracks GIL acquisition patterns across a session."""

    def __init__(self) -> None:
        self._stats = GILStats()
        self._guards: list[GILGuard] = []

    def acquire(self, mode: GILAcquireMode = GILAcquireMode.PYTHON) -> GILGuard:
        guard = GILGuard(mode=mode)
        self._guards.append(guard)
        self._stats.total_acquisitions += 1
        return guard

    def release(self, guard: GILGuard) -> None:
        hold = guard.hold_duration_ms()
        guard.release()
        self._stats.record_acquisition(hold)
        self._stats.record_release()

    def stats(self) -> GILStats:
        return GILStats(
            total_acquisitions=self._stats.total_acquisitions,
            total_releases=self._stats.total_releases,
            total_hold_time_ms=self._stats.total_hold_time_ms,
            max_hold_time_ms=self._stats.max_hold_time_ms,
            allow_threads_calls=self._stats.allow_threads_calls,
            contention_events=self._stats.contention_events,
        )

    def active_guards(self) -> list[GILGuard]:
        return [g for g in self._guards if g.is_active()]

    def allow_threads_count(self) -> int:
        return self._stats.allow_threads_calls


@dataclass
class NoGILContext:
    """Models a no-GIL (allow_threads) execution context."""

    label: str
    reason: str = ""
    estimated_duration_ms: float = 0.0
    _entered: bool = field(default=False, init=False)
    _exited: bool = field(default=False, init=False)

    @contextmanager
    def enter(self) -> Generator[NoGILContext, None, None]:
        self._entered = True
        try:
            yield self
        finally:
            self._exited = True

    def is_suitable_for_nogil(self) -> bool:
        """True if operation is long enough to justify releasing the GIL."""
        return self.estimated_duration_ms > 1.0

    def was_entered(self) -> bool:
        return self._entered
