"""Demonstrates PyO3ModuleBuilder and FunctionSpec to build a Rust extension module skeleton.

Shows five patterns:
1. plain function
2. class (#[pyclass])
3. enum (#[pyclass] with enum-like variants)
4. iterator (#[pyclass] implementing __iter__/__next__)
5. async function (#[pyo3(signature=...)] + pyo3-asyncio)
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from patterns.module_builder import (
    DocStyle,
    PyO3Class,
    PyO3Function,
    PyO3Module,
    PyO3ModuleBuilder,
)
from patterns.type_mapping import PyO3Type


# ---------------------------------------------------------------------------
# Pattern 1 – plain free function
# ---------------------------------------------------------------------------

def make_sum_function() -> PyO3Function:
    """Return a FunctionSpec for a simple sum-of-list function."""
    fn = PyO3Function(
        name="fast_sum",
        return_type=PyO3Type.FLOAT,
        doc="Sum a list of floats using Rust for maximum throughput.",
        releases_gil=True,
    )
    fn.add_param("values", PyO3Type.LIST)
    return fn


# ---------------------------------------------------------------------------
# Pattern 2 – class (#[pyclass])
# ---------------------------------------------------------------------------

def make_matrix_class() -> PyO3Class:
    """Return a ClassSpec for a 2-D matrix backed by a Rust Vec<f64>."""
    cls = PyO3Class(
        name="Matrix",
        doc="A dense 2-D matrix stored as a flat Rust Vec<f64>.",
        frozen=False,
    )
    cls.add_property("rows", PyO3Type.INT)
    cls.add_property("cols", PyO3Type.INT)

    new_fn = PyO3Function(name="__init__", return_type=PyO3Type.NONE)
    new_fn.add_param("rows", PyO3Type.INT)
    new_fn.add_param("cols", PyO3Type.INT)

    dot_fn = PyO3Function(name="dot", return_type=PyO3Type.ANY, releases_gil=True)
    dot_fn.add_param("other", PyO3Type.ANY)

    transpose_fn = PyO3Function(name="transpose", return_type=PyO3Type.ANY, releases_gil=True)

    cls.add_method(new_fn).add_method(dot_fn).add_method(transpose_fn)
    return cls


# ---------------------------------------------------------------------------
# Pattern 3 – enum-like class
# ---------------------------------------------------------------------------

def make_compression_enum() -> PyO3Class:
    """Return a ClassSpec modelling a Rust enum exposed as a Python class."""
    cls = PyO3Class(
        name="CompressionLevel",
        doc="Mirrors the Rust CompressionLevel enum via #[pyclass].",
        frozen=True,
    )
    # Enum variants become class-level constants in the stub.
    cls.add_property("NONE", PyO3Type.INT)
    cls.add_property("FAST", PyO3Type.INT)
    cls.add_property("BEST", PyO3Type.INT)

    from_int = PyO3Function(name="from_int", return_type=PyO3Type.ANY)
    from_int.add_param("level", PyO3Type.INT)
    cls.add_method(from_int)
    return cls


# ---------------------------------------------------------------------------
# Pattern 4 – iterator class
# ---------------------------------------------------------------------------

def make_chunk_iterator_class() -> PyO3Class:
    """Return a ClassSpec for a chunked iterator over a bytes buffer."""
    cls = PyO3Class(
        name="ChunkIterator",
        doc="Yields fixed-size byte chunks from a Rust-owned buffer.",
    )
    cls.add_property("chunk_size", PyO3Type.INT)
    cls.add_property("position", PyO3Type.INT)

    init_fn = PyO3Function(name="__init__", return_type=PyO3Type.NONE)
    init_fn.add_param("data", PyO3Type.BYTES)
    init_fn.add_param("chunk_size", PyO3Type.INT)

    iter_fn = PyO3Function(name="__iter__", return_type=PyO3Type.ANY)
    next_fn = PyO3Function(name="__next__", return_type=PyO3Type.BYTES)

    cls.add_method(init_fn).add_method(iter_fn).add_method(next_fn)
    return cls


# ---------------------------------------------------------------------------
# Pattern 5 – async function
# ---------------------------------------------------------------------------

def make_async_fetch_function() -> PyO3Function:
    """Return a FunctionSpec for a Tokio-backed async HTTP-fetch wrapper."""
    fn = PyO3Function(
        name="async_fetch",
        return_type=PyO3Type.BYTES,
        doc="Fetch a URL asynchronously using the Tokio runtime via pyo3-asyncio.",
        is_async=True,
        releases_gil=True,
    )
    fn.add_param("url", PyO3Type.STR)
    fn.add_param("timeout_ms", PyO3Type.INT)
    return fn


# ---------------------------------------------------------------------------
# Module assembly
# ---------------------------------------------------------------------------

def build_demo_module() -> PyO3Module:
    """Assemble all five patterns into one PyO3Module."""
    return (
        PyO3ModuleBuilder("fast_ops")
        .doc("PyO3-powered extension module demonstrating five Rust/Python patterns.")
        .version("0.2.0")
        .function(make_sum_function())
        .function(make_async_fetch_function())
        .cls(make_matrix_class())
        .cls(make_compression_enum())
        .cls(make_chunk_iterator_class())
        .submodule("fast_ops._internal")
        .build()
    )


# ---------------------------------------------------------------------------
# Code generators
# ---------------------------------------------------------------------------

def generate_cargo_toml(module: PyO3Module) -> str:
    """Render a minimal Cargo.toml for the module."""
    return textwrap.dedent(f"""\
        [package]
        name = "{module.name}"
        version = "{module.version}"
        edition = "2021"

        [lib]
        name = "{module.name}"
        crate-type = ["cdylib"]

        [dependencies]
        pyo3 = {{ version = "0.21", features = ["extension-module"] }}
        pyo3-asyncio = {{ version = "0.21", features = ["tokio-runtime"] }}
        tokio = {{ version = "1", features = ["full"] }}
    """)


def generate_pyproject_toml(module: PyO3Module) -> str:
    """Render a minimal pyproject.toml that uses maturin as the build backend."""
    return textwrap.dedent(f"""\
        [build-system]
        requires = ["maturin>=1.5,<2.0"]
        build-backend = "maturin"

        [project]
        name = "{module.name}"
        version = "{module.version}"
        requires-python = ">=3.10"

        [tool.maturin]
        features = ["pyo3/extension-module"]
    """)


def generate_rust_skeleton(module: PyO3Module) -> str:
    """Render a Rust src/lib.rs skeleton with stubs for all symbols."""
    lines: list[str] = [
        "use pyo3::prelude::*;",
        "",
        "/// PyO3 module entry point.",
        f"#[pymodule]",
        f"fn {module.name}(m: &Bound<'_, PyModule>) -> PyResult<()> {{",
    ]

    for fn_obj in module.functions:
        lines.append(f"    m.add_function(wrap_pyfunction!({fn_obj.name}, m)?)?;")
    for cls_obj in module.classes:
        lines.append(f"    m.add_class::<{cls_obj.name}>()?;")
    lines += ["    Ok(())", "}", ""]

    for fn_obj in module.functions:
        prefix = "async " if fn_obj.is_async else ""
        params = ", ".join(f"{n}: {t.value}" for n, t in fn_obj.params)
        ret = fn_obj.return_type.value
        lines += [
            f"/// {fn_obj.doc}" if fn_obj.doc else f"/// {fn_obj.name}",
            "#[pyfunction]",
            f"pub {prefix}fn {fn_obj.name}({params}) -> PyResult<{ret}> {{",
            "    todo!()",
            "}",
            "",
        ]

    for cls_obj in module.classes:
        attrs = "#[pyclass(frozen)]" if cls_obj.frozen else "#[pyclass]"
        lines += [
            f"/// {cls_obj.doc}" if cls_obj.doc else f"/// {cls_obj.name}",
            attrs,
            f"pub struct {cls_obj.name} {{",
        ]
        for prop_name, prop_type in cls_obj.properties:
            lines.append(f"    pub {prop_name}: {prop_type.value},  // Python {prop_type.value}")
        lines += ["}", "", "#[pymethods]", f"impl {cls_obj.name} {{"]
        for method in cls_obj.methods:
            m_params = ", ".join(f"{n}: {t.value}" for n, t in method.params)
            lines += [
                f"    pub fn {method.name}(&self, {m_params}) -> PyResult<{method.return_type.value}> {{",
                "        todo!()",
                "    }",
            ]
        lines += ["}", ""]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Build the module and print generated artifacts."""
    module = build_demo_module()

    print("=" * 72)
    print(f"Module: {module.name}  v{module.version}")
    print(f"  {module.function_count()} functions, {module.class_count()} classes")
    print(f"  symbols: {module.symbol_names()}")
    print("=" * 72)

    print("\n--- Cargo.toml ---")
    print(generate_cargo_toml(module))

    print("--- pyproject.toml ---")
    print(generate_pyproject_toml(module))

    print("--- src/lib.rs (skeleton) ---")
    print(generate_rust_skeleton(module))

    print("--- Python stubs ---")
    for cls in module.classes:
        print(cls.python_stub(style=DocStyle.PLAIN))
        print()

    print("--- Function signatures ---")
    for fn in module.functions:
        print(" ", fn.python_signature())


if __name__ == "__main__":
    main()
