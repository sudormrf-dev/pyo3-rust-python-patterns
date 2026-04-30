"""Demonstrates TypeMapper for converting Python ↔ Rust types via PyO3.

Covers:
- All primitive mappings from the default registry
- Difficult generic cases: Optional[T], List[T], Dict[K, V], Tuple[...], Union[A, B]
- Generated Rust conversion stubs for each complex type
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from patterns.type_mapping import (
    PyO3Type,
    RustPrimitive,
    TypeMapping,
    TypeMappingRegistry,
    rust_type_to_python,
)


# ---------------------------------------------------------------------------
# Extended registry with complex / generic types
# ---------------------------------------------------------------------------


def build_extended_registry() -> TypeMappingRegistry:
    """Return a registry enriched with generic and container type mappings."""
    registry = TypeMappingRegistry()

    # Zero-copy byte slice – the most important performance mapping
    registry.register(
        TypeMapping(
            rust_type="&[u8]",
            python_type=PyO3Type.BYTES,
            notes="Zero-copy via PyBytes::from_data; no allocation on the Rust side.",
            zero_copy=True,
        )
    )

    # Owned string – always clones
    registry.register(
        TypeMapping(
            rust_type="String",
            python_type=PyO3Type.STR,
            notes="Rust owns the UTF-8 string; PyO3 copies into a Python str object.",
            requires_clone=True,
        )
    )

    # Option<T> → Optional[T] (represented as PyO3Type.ANY here; annotated separately)
    registry.register(
        TypeMapping(
            rust_type="Option<String>",
            python_type=PyO3Type.STR,
            notes="Option::None → Python None; Option::Some(s) → str.",
        )
    )
    registry.register(
        TypeMapping(
            rust_type="Option<i64>",
            python_type=PyO3Type.INT,
            notes="Option::None → Python None; Option::Some(n) → int.",
        )
    )
    registry.register(
        TypeMapping(
            rust_type="Option<f64>",
            python_type=PyO3Type.FLOAT,
            notes="Option::None → Python None; Option::Some(f) → float.",
        )
    )

    # Vec<T> → list
    registry.register(
        TypeMapping(
            rust_type="Vec<String>",
            python_type=PyO3Type.LIST,
            notes="Each String cloned into a Python str; full allocation per element.",
            requires_clone=True,
        )
    )
    registry.register(
        TypeMapping(
            rust_type="Vec<i64>",
            python_type=PyO3Type.LIST,
            notes="Vec<i64> converted element-by-element to a Python list[int].",
        )
    )
    registry.register(
        TypeMapping(
            rust_type="Vec<f64>",
            python_type=PyO3Type.LIST,
            notes="Consider numpy.ndarray for large float buffers to avoid per-element overhead.",
        )
    )

    # HashMap<K, V> → dict
    registry.register(
        TypeMapping(
            rust_type="HashMap<String, String>",
            python_type=PyO3Type.DICT,
            notes="All keys/values cloned; O(n) allocation.",
            requires_clone=True,
        )
    )
    registry.register(
        TypeMapping(
            rust_type="HashMap<String, i64>",
            python_type=PyO3Type.DICT,
            notes="Keys cloned, integer values converted cheaply.",
            requires_clone=True,
        )
    )

    # Tuples
    registry.register(
        TypeMapping(
            rust_type="(i64, f64)",
            python_type=PyO3Type.TUPLE,
            notes="Fixed-arity Rust tuple → Python tuple via IntoPy.",
        )
    )
    registry.register(
        TypeMapping(
            rust_type="(String, String, i32)",
            python_type=PyO3Type.TUPLE,
            notes="Mixed-type tuple; each element individually converted.",
            requires_clone=True,
        )
    )

    return registry


# ---------------------------------------------------------------------------
# Rust stub generators
# ---------------------------------------------------------------------------


def _option_stub(inner_rust: str, inner_py: str) -> str:
    """Generate a Rust helper that extracts Option<T> into PyResult."""
    return textwrap.dedent(f"""\
        // Option<{inner_rust}> → Optional[{inner_py}]
        pub fn extract_option_{inner_rust.lower().replace("<", "_").replace(">", "")}(
            ob: &Bound<'_, PyAny>,
        ) -> PyResult<Option<{inner_rust}>> {{
            if ob.is_none() {{
                Ok(None)
            }} else {{
                Ok(Some(ob.extract::<{inner_rust}>()?))
            }}
        }}
    """)


def _vec_stub(element_rust: str, element_py: str) -> str:
    """Generate a Rust helper that converts Vec<T> from a Python list."""
    return textwrap.dedent(f"""\
        // Vec<{element_rust}> → list[{element_py}]
        pub fn vec_from_py_{element_rust.lower()}(
            ob: &Bound<'_, PyAny>,
        ) -> PyResult<Vec<{element_rust}>> {{
            ob.extract::<Vec<{element_rust}>>()
        }}
    """)


def _dict_stub(key_rust: str, val_rust: str, val_py: str) -> str:
    """Generate a Rust helper that converts HashMap<K, V> from a Python dict."""
    return textwrap.dedent(f"""\
        // HashMap<{key_rust}, {val_rust}> → dict[str, {val_py}]
        pub fn hashmap_from_py(
            ob: &Bound<'_, PyAny>,
        ) -> PyResult<std::collections::HashMap<{key_rust}, {val_rust}>> {{
            ob.extract::<std::collections::HashMap<{key_rust}, {val_rust}>>()
        }}
    """)


def _tuple_stub(rust_sig: str, py_sig: str) -> str:
    """Generate a Rust helper that converts a fixed-arity tuple."""
    return textwrap.dedent(f"""\
        // Rust {rust_sig} → Python tuple[{py_sig}]
        pub fn tuple_from_py(ob: &Bound<'_, PyAny>) -> PyResult<{rust_sig}> {{
            ob.extract::<{rust_sig}>()
        }}
    """)


def _union_stub(variants: list[tuple[str, str]]) -> str:
    """Generate a Rust helper using an enum to model Union[A, B, ...]."""
    variant_lines = "\n".join(f"    {py}({rust})," for rust, py in variants)
    match_arms = "\n".join(
        f"        if let Ok(v) = ob.extract::<{rust}>() {{ return Ok(MyUnion::{py}(v)); }}"
        for rust, py in variants
    )
    return textwrap.dedent(f"""\
        // Union[{", ".join(py for _, py in variants)}]
        pub enum MyUnion {{
        {variant_lines}
        }}

        pub fn union_from_py(ob: &Bound<'_, PyAny>) -> PyResult<MyUnion> {{
        {match_arms}
            Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>("no variant matched"))
        }}
    """)


# ---------------------------------------------------------------------------
# Demonstration helpers
# ---------------------------------------------------------------------------


def demo_primitives(registry: TypeMappingRegistry) -> None:
    """Print a table of all primitive Rust → Python mappings."""
    print("Primitive type mappings")
    print("-" * 52)
    print(f"  {'Rust type':<20} {'Python type':<12} Cost")
    print(f"  {'-' * 20} {'-' * 12} ------")
    for primitive in RustPrimitive:
        py_type = rust_type_to_python(primitive)
        mapping = registry.get(primitive.value)
        cost = mapping.conversion_cost() if mapping else "convert"
        print(f"  {primitive.value:<20} {py_type.value:<12} {cost}")
    print()


def demo_complex_cases(registry: TypeMappingRegistry) -> None:
    """Print analysis of the difficult generic/container types."""
    complex_keys = [
        "Option<String>",
        "Option<i64>",
        "Option<f64>",
        "Vec<String>",
        "Vec<i64>",
        "Vec<f64>",
        "HashMap<String, String>",
        "HashMap<String, i64>",
        "(i64, f64)",
        "(String, String, i32)",
    ]

    print("Complex / generic type mappings")
    print("-" * 72)
    print(f"  {'Rust type':<32} {'Python type':<10} {'Cost':<12} Notes")
    print(f"  {'-' * 32} {'-' * 10} {'-' * 12} -----")
    for key in complex_keys:
        m = registry.get(key)
        if m:
            short_notes = m.notes[:38] + "…" if len(m.notes) > 38 else m.notes
            print(
                f"  {m.rust_type:<32} {m.python_type.value:<10} {m.conversion_cost():<12} {short_notes}"
            )
    print()


def demo_conversion_stubs() -> None:
    """Print generated Rust stubs for each difficult pattern."""
    print("Generated Rust conversion stubs")
    print("=" * 72)

    print("\n[1] Optional[str]  –  Option<String>")
    print(_option_stub("String", "str"))

    print("[2] Optional[int]  –  Option<i64>")
    print(_option_stub("i64", "int"))

    print("[3] list[str]  –  Vec<String>")
    print(_vec_stub("String", "str"))

    print("[4] list[float]  –  Vec<f64>")
    print(_vec_stub("f64", "float"))

    print("[5] dict[str, str]  –  HashMap<String, String>")
    print(_dict_stub("String", "String", "str"))

    print("[6] dict[str, int]  –  HashMap<String, i64>")
    print(_dict_stub("String", "i64", "int"))

    print("[7] tuple[int, float]  –  (i64, f64)")
    print(_tuple_stub("(i64, f64)", "int, float"))

    print("[8] Union[str, int, float]")
    print(_union_stub([("String", "Str"), ("i64", "Int"), ("f64", "Float")]))


def demo_registry_stats(registry: TypeMappingRegistry) -> None:
    """Print high-level stats about the registry."""
    print("Registry statistics")
    print("-" * 40)
    print(f"  Total mappings : {registry.mapping_count()}")
    print(f"  Zero-copy types: {len(registry.zero_copy_types())}")
    py_types_used = sorted(t.value for t in registry.python_types_used())
    print(f"  Python types   : {', '.join(py_types_used)}")
    print()

    annotation_map = registry.to_annotation_map()
    zero_copies = registry.zero_copy_types()
    if zero_copies:
        print("  Zero-copy mappings (highlight):")
        for m in zero_copies:
            print(f"    {m.rust_type} → {annotation_map.get(m.rust_type, '?')}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run all type-mapping demonstrations."""
    registry = build_extended_registry()

    print("=" * 72)
    print("PyO3 Type Mapping Demo")
    print("=" * 72)
    print()

    demo_registry_stats(registry)
    demo_primitives(registry)
    demo_complex_cases(registry)
    demo_conversion_stubs()


if __name__ == "__main__":
    main()
