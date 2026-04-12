"""PyO3 type mapping patterns between Rust and Python types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RustPrimitive(str, Enum):
    """Rust primitive types."""

    I8 = "i8"
    I16 = "i16"
    I32 = "i32"
    I64 = "i64"
    I128 = "i128"
    ISIZE = "isize"
    U8 = "u8"
    U16 = "u16"
    U32 = "u32"
    U64 = "u64"
    U128 = "u128"
    USIZE = "usize"
    F32 = "f32"
    F64 = "f64"
    BOOL = "bool"
    STR = "str"
    STRING = "String"
    BYTES = "&[u8]"
    UNIT = "()"

    def is_integer(self) -> bool:
        return self in {
            RustPrimitive.I8,
            RustPrimitive.I16,
            RustPrimitive.I32,
            RustPrimitive.I64,
            RustPrimitive.I128,
            RustPrimitive.ISIZE,
            RustPrimitive.U8,
            RustPrimitive.U16,
            RustPrimitive.U32,
            RustPrimitive.U64,
            RustPrimitive.U128,
            RustPrimitive.USIZE,
        }

    def is_signed(self) -> bool:
        return self in {
            RustPrimitive.I8,
            RustPrimitive.I16,
            RustPrimitive.I32,
            RustPrimitive.I64,
            RustPrimitive.I128,
            RustPrimitive.ISIZE,
        }

    def is_float(self) -> bool:
        return self in {RustPrimitive.F32, RustPrimitive.F64}


class PyO3Type(str, Enum):
    """Python types as seen from PyO3."""

    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STR = "str"
    BYTES = "bytes"
    LIST = "list"
    DICT = "dict"
    TUPLE = "tuple"
    SET = "set"
    NONE = "None"
    ANY = "Any"
    CALLABLE = "Callable"

    def is_collection(self) -> bool:
        return self in {PyO3Type.LIST, PyO3Type.DICT, PyO3Type.TUPLE, PyO3Type.SET}


@dataclass
class TypeMapping:
    """Maps a Rust type to a Python type with conversion notes."""

    rust_type: str
    python_type: PyO3Type
    notes: str = ""
    zero_copy: bool = False
    requires_clone: bool = False
    gil_safe: bool = True

    def conversion_cost(self) -> str:
        if self.zero_copy:
            return "zero-copy"
        if self.requires_clone:
            return "clone"
        return "convert"


# Default mappings for Rust primitives
_DEFAULT_MAPPINGS: dict[RustPrimitive, PyO3Type] = {
    RustPrimitive.I8: PyO3Type.INT,
    RustPrimitive.I16: PyO3Type.INT,
    RustPrimitive.I32: PyO3Type.INT,
    RustPrimitive.I64: PyO3Type.INT,
    RustPrimitive.I128: PyO3Type.INT,
    RustPrimitive.ISIZE: PyO3Type.INT,
    RustPrimitive.U8: PyO3Type.INT,
    RustPrimitive.U16: PyO3Type.INT,
    RustPrimitive.U32: PyO3Type.INT,
    RustPrimitive.U64: PyO3Type.INT,
    RustPrimitive.U128: PyO3Type.INT,
    RustPrimitive.USIZE: PyO3Type.INT,
    RustPrimitive.F32: PyO3Type.FLOAT,
    RustPrimitive.F64: PyO3Type.FLOAT,
    RustPrimitive.BOOL: PyO3Type.BOOL,
    RustPrimitive.STR: PyO3Type.STR,
    RustPrimitive.STRING: PyO3Type.STR,
    RustPrimitive.BYTES: PyO3Type.BYTES,
    RustPrimitive.UNIT: PyO3Type.NONE,
}


def rust_type_to_python(rust_type: RustPrimitive) -> PyO3Type:
    """Return the Python equivalent for a Rust primitive."""
    return _DEFAULT_MAPPINGS[rust_type]


class TypeMappingRegistry:
    """Registry of type mappings for a PyO3 module."""

    def __init__(self) -> None:
        self._mappings: dict[str, TypeMapping] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        for primitive, py_type in _DEFAULT_MAPPINGS.items():
            m = TypeMapping(rust_type=primitive.value, python_type=py_type)
            self._mappings[primitive.value] = m

    def register(self, mapping: TypeMapping) -> None:
        self._mappings[mapping.rust_type] = mapping

    def get(self, rust_type: str) -> TypeMapping | None:
        return self._mappings.get(rust_type)

    def all_mappings(self) -> list[TypeMapping]:
        return list(self._mappings.values())

    def zero_copy_types(self) -> list[TypeMapping]:
        return [m for m in self._mappings.values() if m.zero_copy]

    def python_types_used(self) -> set[PyO3Type]:
        return {m.python_type for m in self._mappings.values()}

    def mapping_count(self) -> int:
        return len(self._mappings)

    def to_annotation_map(self) -> dict[str, Any]:
        return {m.rust_type: m.python_type.value for m in self._mappings.values()}
