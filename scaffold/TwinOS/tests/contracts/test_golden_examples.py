"""계약 golden example 검증 — CI가 Interface Spec v1.0을 강제하는 지점 (10 문서 §3.3).

규칙: contracts/examples/<contract>/<ver>/<schema-name>/<example>.json 은
      contracts/<contract>/<ver>/<schema-name>.schema.json 에 대해 유효해야 한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
EXAMPLES = CONTRACTS / "examples"


def _load_registry() -> Registry:
    registry = Registry()
    for schema_path in CONTRACTS.rglob("*.schema.json"):
        schema = json.loads(schema_path.read_text())
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(uri=schema["$id"], resource=resource)
    return registry


REGISTRY = _load_registry()


def _example_cases():
    for example in sorted(EXAMPLES.rglob("*.json")):
        rel = example.relative_to(EXAMPLES)          # task-api/v1/task-request/x.json
        schema_name = rel.parts[-2]
        schema_path = CONTRACTS / Path(*rel.parts[:-2]) / f"{schema_name}.schema.json"
        yield pytest.param(example, schema_path, id=str(rel))


@pytest.mark.parametrize(("example_path", "schema_path"), list(_example_cases()))
def test_golden_example_validates(example_path: Path, schema_path: Path):
    assert schema_path.exists(), f"schema not found for example: {schema_path}"
    schema = json.loads(schema_path.read_text())
    instance = json.loads(example_path.read_text())
    validator = Draft202012Validator(schema, registry=REGISTRY)
    errors = sorted(validator.iter_errors(instance), key=lambda e: e.json_path)
    assert not errors, "\n".join(f"{e.json_path}: {e.message}" for e in errors)


def test_all_schemas_are_valid_metaschemas():
    for schema_path in CONTRACTS.rglob("*.schema.json"):
        schema = json.loads(schema_path.read_text())
        Draft202012Validator.check_schema(schema)
        assert "$id" in schema, f"missing $id: {schema_path}"
