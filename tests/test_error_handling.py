"""Tests for error_handling.py."""

from __future__ import annotations

from patterns.error_handling import (
    ErrorCategory,
    PyO3Error,
    PyO3ErrorChain,
    RustPanic,
    map_rust_error,
)


class TestErrorCategory:
    def test_panic_maps_to_runtime_error(self):
        assert ErrorCategory.PANIC.python_exception_name() == "RuntimeError"

    def test_value_error_maps_to_itself(self):
        assert ErrorCategory.VALUE_ERROR.python_exception_name() == "ValueError"

    def test_os_error_maps_to_itself(self):
        assert ErrorCategory.OS_ERROR.python_exception_name() == "OSError"


class TestPyO3Error:
    def test_python_repr(self):
        e = PyO3Error("ParseIntError", "invalid digit", ErrorCategory.VALUE_ERROR)
        r = e.python_repr()
        assert "ValueError" in r
        assert "invalid digit" in r

    def test_not_panic(self):
        e = PyO3Error("IoError", "file not found", ErrorCategory.OS_ERROR)
        assert e.is_panic() is False

    def test_is_panic(self):
        e = PyO3Error("panic", "out of bounds", ErrorCategory.PANIC)
        assert e.is_panic() is True

    def test_with_context(self):
        e = PyO3Error("TryFromIntError", "overflow", ErrorCategory.OVERFLOW_ERROR)
        e.with_context("value", 999)
        assert e.context["value"] == 999

    def test_to_dict(self):
        e = PyO3Error("ParseIntError", "bad", ErrorCategory.VALUE_ERROR)
        d = e.to_dict()
        assert d["rust_type"] == "ParseIntError"
        assert d["category"] == "ValueError"


class TestRustPanic:
    def test_to_pyo3_error(self):
        p = RustPanic("index out of bounds: len=5, idx=10", "src/lib.rs:42")
        e = p.to_pyo3_error()
        assert e.is_panic() is True
        assert e.cause == "src/lib.rs:42"

    def test_safe_message_first_line(self):
        p = RustPanic("panic message\ndetailed backtrace")
        assert p.safe_message() == "panic message"

    def test_empty_message(self):
        p = RustPanic("")
        assert p.safe_message() == "Rust panic occurred"


class TestPyO3ErrorChain:
    def test_empty_chain(self):
        chain = PyO3ErrorChain()
        assert chain.primary_error() is None
        assert chain.root_cause() is None

    def test_add_and_primary(self):
        chain = PyO3ErrorChain()
        e = PyO3Error("IoError", "file not found", ErrorCategory.OS_ERROR)
        chain.add(e)
        assert chain.primary_error() is e

    def test_root_cause_last(self):
        chain = PyO3ErrorChain()
        e1 = PyO3Error("Outer", "msg1", ErrorCategory.RUNTIME_ERROR)
        e2 = PyO3Error("Inner", "msg2", ErrorCategory.VALUE_ERROR)
        chain.add(e1)
        chain.add(e2)
        assert chain.root_cause() is e2

    def test_has_panic(self):
        chain = PyO3ErrorChain()
        chain.add(PyO3Error("panic", "boom", ErrorCategory.PANIC))
        assert chain.has_panic() is True

    def test_no_panic(self):
        chain = PyO3ErrorChain()
        chain.add(PyO3Error("IoError", "err", ErrorCategory.OS_ERROR))
        assert chain.has_panic() is False

    def test_depth(self):
        chain = PyO3ErrorChain()
        chain.add(PyO3Error("A", "a", ErrorCategory.RUNTIME_ERROR))
        chain.add(PyO3Error("B", "b", ErrorCategory.RUNTIME_ERROR))
        assert chain.depth() == 2

    def test_category_counts(self):
        chain = PyO3ErrorChain()
        chain.add(PyO3Error("A", "a", ErrorCategory.VALUE_ERROR))
        chain.add(PyO3Error("B", "b", ErrorCategory.VALUE_ERROR))
        chain.add(PyO3Error("C", "c", ErrorCategory.OS_ERROR))
        counts = chain.category_counts()
        assert counts["ValueError"] == 2
        assert counts["OSError"] == 1

    def test_chaining_returns_self(self):
        chain = PyO3ErrorChain()
        e = PyO3Error("X", "x", ErrorCategory.RUNTIME_ERROR)
        assert chain.add(e) is chain


class TestMapRustError:
    def test_parse_int_error(self):
        e = map_rust_error("ParseIntError", "invalid digit found")
        assert e.category == ErrorCategory.VALUE_ERROR

    def test_io_error(self):
        e = map_rust_error("IoError", "permission denied")
        assert e.category == ErrorCategory.OS_ERROR

    def test_overflow_error(self):
        e = map_rust_error("TryFromIntError", "out of range")
        assert e.category == ErrorCategory.OVERFLOW_ERROR

    def test_unknown_defaults_runtime(self):
        e = map_rust_error("UnknownError", "something")
        assert e.category == ErrorCategory.RUNTIME_ERROR
