"""Tests for gil_patterns.py."""

from __future__ import annotations

import time

from patterns.gil_patterns import (
    GILAcquireMode,
    GILGuard,
    GILStats,
    GILTracker,
    NoGILContext,
)


class TestGILAcquireMode:
    def test_allow_threads_releases_gil(self):
        assert GILAcquireMode.ALLOW_THREADS.releases_gil() is True

    def test_python_does_not_release(self):
        assert GILAcquireMode.PYTHON.releases_gil() is False


class TestGILGuard:
    def test_active_initially(self):
        g = GILGuard()
        assert g.is_active() is True

    def test_release(self):
        g = GILGuard()
        g.release()
        assert g.is_active() is False

    def test_hold_duration_nonnegative(self):
        g = GILGuard()
        time.sleep(0.01)
        g.release()
        assert g.hold_duration_ms() >= 0


class TestGILStats:
    def test_mean_hold_no_acquisitions(self):
        s = GILStats()
        assert s.mean_hold_time_ms() == 0.0

    def test_record_acquisition(self):
        s = GILStats()
        s.record_acquisition(5.0)
        s.record_acquisition(15.0)
        assert s.total_acquisitions == 2
        assert s.mean_hold_time_ms() == 10.0

    def test_max_hold_time(self):
        s = GILStats()
        s.record_acquisition(5.0)
        s.record_acquisition(50.0)
        assert s.max_hold_time_ms == 50.0

    def test_not_contended_low_hold(self):
        s = GILStats()
        s.record_acquisition(1.0)
        assert s.is_contended() is False

    def test_contended_high_hold(self):
        s = GILStats()
        s.record_acquisition(100.0)
        assert s.is_contended() is True

    def test_contended_by_events(self):
        s = GILStats(contention_events=1)
        assert s.is_contended() is True


class TestGILTracker:
    def test_acquire_returns_guard(self):
        tracker = GILTracker()
        guard = tracker.acquire()
        assert isinstance(guard, GILGuard)

    def test_acquire_increments_stats(self):
        tracker = GILTracker()
        tracker.acquire()
        assert tracker.stats().total_acquisitions == 1

    def test_release_updates_stats(self):
        tracker = GILTracker()
        guard = tracker.acquire()
        tracker.release(guard)
        assert tracker.stats().total_releases == 1

    def test_active_guards(self):
        tracker = GILTracker()
        g1 = tracker.acquire()
        g2 = tracker.acquire()
        tracker.release(g1)
        active = tracker.active_guards()
        assert g2 in active
        assert g1 not in active

    def test_allow_threads_count(self):
        tracker = GILTracker()
        assert tracker.allow_threads_count() == 0


class TestNoGILContext:
    def test_not_entered_initially(self):
        ctx = NoGILContext("compute")
        assert ctx.was_entered() is False

    def test_enter_context_manager(self):
        ctx = NoGILContext("compute", estimated_duration_ms=10.0)
        with ctx.enter():
            assert ctx.was_entered() is True

    def test_suitable_for_nogil_long(self):
        ctx = NoGILContext("long_op", estimated_duration_ms=100.0)
        assert ctx.is_suitable_for_nogil() is True

    def test_not_suitable_short(self):
        ctx = NoGILContext("quick", estimated_duration_ms=0.5)
        assert ctx.is_suitable_for_nogil() is False
