"""PyO3 error handling patterns: Rust errors → Python exceptions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    """Categories of errors that cross the Rust/Python boundary."""

    VALUE_ERROR = "ValueError"
    TYPE_ERROR = "TypeError"
    RUNTIME_ERROR = "RuntimeError"
    OS_ERROR = "OSError"
    OVERFLOW_ERROR = "OverflowError"
    INDEX_ERROR = "IndexError"
    KEY_ERROR = "KeyError"
    NOT_IMPLEMENTED = "NotImplementedError"
    MEMORY_ERROR = "MemoryError"
    PANIC = "panic"

    def python_exception_name(self) -> str:
        if self == ErrorCategory.PANIC:
            return "RuntimeError"
        return str(self.value)


@dataclass
class PyO3Error:
    """A Rust error mapped to a Python exception."""

    rust_type: str
    message: str
    category: ErrorCategory = ErrorCategory.RUNTIME_ERROR
    context: dict[str, Any] = field(default_factory=dict)
    cause: str | None = None

    def python_repr(self) -> str:
        exc = self.category.python_exception_name()
        return f"{exc}({self.message!r})"

    def with_context(self, key: str, value: Any) -> PyO3Error:
        self.context[key] = value
        return self

    def is_panic(self) -> bool:
        return self.category == ErrorCategory.PANIC

    def to_dict(self) -> dict[str, Any]:
        return {
            "rust_type": self.rust_type,
            "message": self.message,
            "category": self.category.value,
            "context": self.context,
            "cause": self.cause,
        }


@dataclass
class RustPanic:
    """Represents a Rust panic that was caught at the PyO3 boundary."""

    message: str
    location: str | None = None
    backtrace: str | None = None

    def to_pyo3_error(self) -> PyO3Error:
        return PyO3Error(
            rust_type="panic",
            message=self.message,
            category=ErrorCategory.PANIC,
            cause=self.location,
        )

    def safe_message(self) -> str:
        """Return message stripped of internal details for user-facing output."""
        first = self.message.split("\n")[0]
        return first if first else "Rust panic occurred"


@dataclass
class PyO3ErrorChain:
    """Chain of errors from Rust through the PyO3 boundary."""

    errors: list[PyO3Error] = field(default_factory=list)

    def add(self, error: PyO3Error) -> PyO3ErrorChain:
        self.errors.append(error)
        return self

    def root_cause(self) -> PyO3Error | None:
        return self.errors[-1] if self.errors else None

    def primary_error(self) -> PyO3Error | None:
        return self.errors[0] if self.errors else None

    def has_panic(self) -> bool:
        return any(e.is_panic() for e in self.errors)

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.errors:
            key = e.category.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def depth(self) -> int:
        return len(self.errors)


# Error mapping table: Rust error type → Python category
_RUST_TO_PYTHON: dict[str, ErrorCategory] = {
    "ParseIntError": ErrorCategory.VALUE_ERROR,
    "ParseFloatError": ErrorCategory.VALUE_ERROR,
    "Utf8Error": ErrorCategory.VALUE_ERROR,
    "FromUtf8Error": ErrorCategory.VALUE_ERROR,
    "TryFromIntError": ErrorCategory.OVERFLOW_ERROR,
    "IndexOutOfBounds": ErrorCategory.INDEX_ERROR,
    "NulError": ErrorCategory.VALUE_ERROR,
    "IoError": ErrorCategory.OS_ERROR,
    "NotFound": ErrorCategory.OS_ERROR,
    "PermissionDenied": ErrorCategory.OS_ERROR,
}


def map_rust_error(rust_type: str, message: str) -> PyO3Error:
    """Map a Rust error type name to a PyO3Error with the right Python category."""
    category = _RUST_TO_PYTHON.get(rust_type, ErrorCategory.RUNTIME_ERROR)
    return PyO3Error(rust_type=rust_type, message=message, category=category)
