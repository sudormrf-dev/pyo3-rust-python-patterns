"""PyO3 module builder: models the structure of a Rust extension module."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from patterns.type_mapping import PyO3Type


class DocStyle(str, Enum):
    """Documentation style for generated stubs."""

    NUMPY = "numpy"
    GOOGLE = "google"
    RST = "rst"
    PLAIN = "plain"


@dataclass
class PyO3Function:
    """Represents a #[pyfunction] exported from Rust."""

    name: str
    return_type: PyO3Type = PyO3Type.ANY
    params: list[tuple[str, PyO3Type]] = field(default_factory=list)
    doc: str = ""
    is_async: bool = False
    releases_gil: bool = False
    signature_override: str | None = None

    def add_param(self, name: str, typ: PyO3Type) -> PyO3Function:
        self.params.append((name, typ))
        return self

    def python_signature(self) -> str:
        if self.signature_override:
            return self.signature_override
        args = ", ".join(f"{n}: {t.value}" for n, t in self.params)
        ret = self.return_type.value
        prefix = "async " if self.is_async else ""
        return f"{prefix}def {self.name}({args}) -> {ret}: ..."

    def param_count(self) -> int:
        return len(self.params)


@dataclass
class PyO3Class:
    """Represents a #[pyclass] exported from Rust."""

    name: str
    doc: str = ""
    methods: list[PyO3Function] = field(default_factory=list)
    properties: list[tuple[str, PyO3Type]] = field(default_factory=list)
    is_subclass: bool = False
    base_class: str | None = None
    frozen: bool = False
    sequence: bool = False

    def add_method(self, method: PyO3Function) -> PyO3Class:
        self.methods.append(method)
        return self

    def add_property(self, name: str, typ: PyO3Type) -> PyO3Class:
        self.properties.append((name, typ))
        return self

    def method_count(self) -> int:
        return len(self.methods)

    def property_count(self) -> int:
        return len(self.properties)

    def python_stub(self, style: DocStyle = DocStyle.PLAIN) -> str:
        base = f"({self.base_class})" if self.base_class else ""
        lines = [f"class {self.name}{base}:"]
        if self.doc:
            lines.append(f'    """{self.doc}"""')
        for prop_name, prop_type in self.properties:
            lines.append(f"    {prop_name}: {prop_type.value}")
        lines.extend(f"    {method.python_signature()}" for method in self.methods)
        if not self.properties and not self.methods:
            lines.append("    ...")
        return "\n".join(lines)


@dataclass
class PyO3Module:
    """Represents a complete #[pymodule]."""

    name: str
    doc: str = ""
    functions: list[PyO3Function] = field(default_factory=list)
    classes: list[PyO3Class] = field(default_factory=list)
    submodules: list[str] = field(default_factory=list)
    version: str = "0.1.0"

    def add_function(self, fn: PyO3Function) -> PyO3Module:
        self.functions.append(fn)
        return self

    def add_class(self, cls: PyO3Class) -> PyO3Module:
        self.classes.append(cls)
        return self

    def add_submodule(self, name: str) -> PyO3Module:
        self.submodules.append(name)
        return self

    def function_count(self) -> int:
        return len(self.functions)

    def class_count(self) -> int:
        return len(self.classes)

    def total_method_count(self) -> int:
        return sum(c.method_count() for c in self.classes)

    def symbol_names(self) -> list[str]:
        names: list[str] = [f.name for f in self.functions]
        names.extend(c.name for c in self.classes)
        names.extend(self.submodules)
        return sorted(names)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "functions": [f.name for f in self.functions],
            "classes": [c.name for c in self.classes],
            "submodules": self.submodules,
        }


class PyO3ModuleBuilder:
    """Fluent builder for PyO3Module."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._doc = ""
        self._functions: list[PyO3Function] = []
        self._classes: list[PyO3Class] = []
        self._submodules: list[str] = []
        self._version = "0.1.0"

    def doc(self, text: str) -> PyO3ModuleBuilder:
        self._doc = text
        return self

    def version(self, v: str) -> PyO3ModuleBuilder:
        self._version = v
        return self

    def function(self, fn: PyO3Function) -> PyO3ModuleBuilder:
        self._functions.append(fn)
        return self

    def cls(self, c: PyO3Class) -> PyO3ModuleBuilder:
        self._classes.append(c)
        return self

    def submodule(self, name: str) -> PyO3ModuleBuilder:
        self._submodules.append(name)
        return self

    def build(self) -> PyO3Module:
        return PyO3Module(
            name=self._name,
            doc=self._doc,
            functions=list(self._functions),
            classes=list(self._classes),
            submodules=list(self._submodules),
            version=self._version,
        )
