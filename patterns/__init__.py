"""PyO3 Rust-Python interop patterns (pure Python modeling layer)."""

from __future__ import annotations

from patterns.error_handling import (
    ErrorCategory,
    PyO3Error,
    PyO3ErrorChain,
    RustPanic,
    map_rust_error,
)
from patterns.gil_patterns import (
    GILAcquireMode,
    GILGuard,
    GILStats,
    GILTracker,
    NoGILContext,
)
from patterns.module_builder import (
    DocStyle,
    PyO3Class,
    PyO3Function,
    PyO3Module,
    PyO3ModuleBuilder,
)
from patterns.type_mapping import (
    PyO3Type,
    RustPrimitive,
    TypeMapping,
    TypeMappingRegistry,
    rust_type_to_python,
)

__all__ = [
    "DocStyle",
    "ErrorCategory",
    "GILAcquireMode",
    "GILGuard",
    "GILStats",
    "GILTracker",
    "NoGILContext",
    "PyO3Class",
    "PyO3Error",
    "PyO3ErrorChain",
    "PyO3Function",
    "PyO3Module",
    "PyO3ModuleBuilder",
    "PyO3Type",
    "RustPanic",
    "RustPrimitive",
    "TypeMapping",
    "TypeMappingRegistry",
    "map_rust_error",
    "rust_type_to_python",
]
