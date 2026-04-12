"""Tests for type_mapping.py."""

from __future__ import annotations

from patterns.type_mapping import (
    PyO3Type,
    RustPrimitive,
    TypeMapping,
    TypeMappingRegistry,
    rust_type_to_python,
)


class TestRustPrimitive:
    def test_i32_is_integer(self):
        assert RustPrimitive.I32.is_integer() is True

    def test_f64_not_integer(self):
        assert RustPrimitive.F64.is_integer() is False

    def test_i64_is_signed(self):
        assert RustPrimitive.I64.is_signed() is True

    def test_u32_not_signed(self):
        assert RustPrimitive.U32.is_signed() is False

    def test_f32_is_float(self):
        assert RustPrimitive.F32.is_float() is True

    def test_bool_not_float(self):
        assert RustPrimitive.BOOL.is_float() is False

    def test_unit_not_integer(self):
        assert RustPrimitive.UNIT.is_integer() is False


class TestPyO3Type:
    def test_list_is_collection(self):
        assert PyO3Type.LIST.is_collection() is True

    def test_int_not_collection(self):
        assert PyO3Type.INT.is_collection() is False

    def test_dict_is_collection(self):
        assert PyO3Type.DICT.is_collection() is True

    def test_tuple_is_collection(self):
        assert PyO3Type.TUPLE.is_collection() is True


class TestRustTypeToPython:
    def test_i32_to_int(self):
        assert rust_type_to_python(RustPrimitive.I32) == PyO3Type.INT

    def test_f64_to_float(self):
        assert rust_type_to_python(RustPrimitive.F64) == PyO3Type.FLOAT

    def test_bool_to_bool(self):
        assert rust_type_to_python(RustPrimitive.BOOL) == PyO3Type.BOOL

    def test_string_to_str(self):
        assert rust_type_to_python(RustPrimitive.STRING) == PyO3Type.STR

    def test_bytes_to_bytes(self):
        assert rust_type_to_python(RustPrimitive.BYTES) == PyO3Type.BYTES

    def test_unit_to_none(self):
        assert rust_type_to_python(RustPrimitive.UNIT) == PyO3Type.NONE


class TestTypeMapping:
    def test_zero_copy_cost(self):
        m = TypeMapping("&[u8]", PyO3Type.BYTES, zero_copy=True)
        assert m.conversion_cost() == "zero-copy"

    def test_clone_cost(self):
        m = TypeMapping("String", PyO3Type.STR, requires_clone=True)
        assert m.conversion_cost() == "clone"

    def test_convert_cost_default(self):
        m = TypeMapping("i32", PyO3Type.INT)
        assert m.conversion_cost() == "convert"


class TestTypeMappingRegistry:
    def test_default_count_positive(self):
        reg = TypeMappingRegistry()
        assert reg.mapping_count() > 0

    def test_get_i32(self):
        reg = TypeMappingRegistry()
        m = reg.get("i32")
        assert m is not None
        assert m.python_type == PyO3Type.INT

    def test_register_custom(self):
        reg = TypeMappingRegistry()
        custom = TypeMapping("MyType", PyO3Type.DICT)
        reg.register(custom)
        assert reg.get("MyType") is not None

    def test_zero_copy_types(self):
        reg = TypeMappingRegistry()
        reg.register(TypeMapping("Buffer", PyO3Type.BYTES, zero_copy=True))
        zc = reg.zero_copy_types()
        assert any(m.rust_type == "Buffer" for m in zc)

    def test_python_types_used_contains_int(self):
        reg = TypeMappingRegistry()
        assert PyO3Type.INT in reg.python_types_used()

    def test_annotation_map_type(self):
        reg = TypeMappingRegistry()
        ann = reg.to_annotation_map()
        assert isinstance(ann, dict)
        assert ann["i32"] == "int"
