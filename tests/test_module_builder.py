"""Tests for module_builder.py."""

from __future__ import annotations

from patterns.module_builder import (
    DocStyle,
    PyO3Class,
    PyO3Function,
    PyO3Module,
    PyO3ModuleBuilder,
)
from patterns.type_mapping import PyO3Type


class TestPyO3Function:
    def test_python_signature_no_args(self):
        fn = PyO3Function("compute", return_type=PyO3Type.INT)
        sig = fn.python_signature()
        assert "def compute()" in sig
        assert "-> int" in sig

    def test_python_signature_with_params(self):
        fn = PyO3Function("add")
        fn.add_param("a", PyO3Type.INT).add_param("b", PyO3Type.INT)
        sig = fn.python_signature()
        assert "a: int" in sig
        assert "b: int" in sig

    def test_async_signature(self):
        fn = PyO3Function("fetch", is_async=True)
        assert fn.python_signature().startswith("async def")

    def test_signature_override(self):
        fn = PyO3Function("foo", signature_override="def foo(*args): ...")
        assert fn.python_signature() == "def foo(*args): ..."

    def test_param_count(self):
        fn = PyO3Function("f")
        fn.add_param("x", PyO3Type.FLOAT)
        assert fn.param_count() == 1

    def test_add_param_returns_self(self):
        fn = PyO3Function("f")
        assert fn.add_param("x", PyO3Type.INT) is fn


class TestPyO3Class:
    def test_stub_has_class_name(self):
        cls = PyO3Class("MyClass")
        stub = cls.python_stub()
        assert "class MyClass" in stub

    def test_stub_with_base(self):
        cls = PyO3Class("Child", base_class="Parent")
        stub = cls.python_stub()
        assert "class Child(Parent)" in stub

    def test_stub_with_doc(self):
        cls = PyO3Class("Thing", doc="A thing.")
        stub = cls.python_stub()
        assert "A thing." in stub

    def test_stub_empty_has_ellipsis(self):
        cls = PyO3Class("Empty")
        assert "..." in cls.python_stub()

    def test_add_method(self):
        cls = PyO3Class("Foo")
        fn = PyO3Function("bar")
        cls.add_method(fn)
        assert cls.method_count() == 1

    def test_add_property(self):
        cls = PyO3Class("Foo")
        cls.add_property("value", PyO3Type.INT)
        assert cls.property_count() == 1

    def test_add_method_returns_self(self):
        cls = PyO3Class("Foo")
        assert cls.add_method(PyO3Function("x")) is cls

    def test_property_in_stub(self):
        cls = PyO3Class("Foo")
        cls.add_property("count", PyO3Type.INT)
        stub = cls.python_stub()
        assert "count: int" in stub


class TestPyO3Module:
    def test_add_function(self):
        m = PyO3Module("mymod")
        m.add_function(PyO3Function("greet"))
        assert m.function_count() == 1

    def test_add_class(self):
        m = PyO3Module("mymod")
        m.add_class(PyO3Class("Widget"))
        assert m.class_count() == 1

    def test_symbol_names_sorted(self):
        m = PyO3Module("mymod")
        m.add_function(PyO3Function("zzz"))
        m.add_function(PyO3Function("aaa"))
        names = m.symbol_names()
        assert names == sorted(names)

    def test_total_method_count(self):
        m = PyO3Module("mymod")
        c = PyO3Class("A")
        c.add_method(PyO3Function("x"))
        c.add_method(PyO3Function("y"))
        m.add_class(c)
        assert m.total_method_count() == 2

    def test_to_dict(self):
        m = PyO3Module("mymod", version="1.0.0")
        d = m.to_dict()
        assert d["name"] == "mymod"
        assert d["version"] == "1.0.0"

    def test_add_submodule(self):
        m = PyO3Module("mymod")
        m.add_submodule("sub")
        assert "sub" in m.symbol_names()


class TestPyO3ModuleBuilder:
    def test_build_returns_module(self):
        m = PyO3ModuleBuilder("testmod").build()
        assert m.name == "testmod"

    def test_doc(self):
        m = PyO3ModuleBuilder("m").doc("My module").build()
        assert m.doc == "My module"

    def test_version(self):
        m = PyO3ModuleBuilder("m").version("2.0.0").build()
        assert m.version == "2.0.0"

    def test_function_added(self):
        fn = PyO3Function("hello")
        m = PyO3ModuleBuilder("m").function(fn).build()
        assert m.function_count() == 1

    def test_class_added(self):
        cls = PyO3Class("Foo")
        m = PyO3ModuleBuilder("m").cls(cls).build()
        assert m.class_count() == 1

    def test_submodule_added(self):
        m = PyO3ModuleBuilder("m").submodule("utils").build()
        assert "utils" in m.submodules

    def test_chaining_returns_self(self):
        b = PyO3ModuleBuilder("m")
        assert b.doc("x") is b

    def test_doc_style_enum_values(self):
        for style in DocStyle:
            assert isinstance(style.value, str)
