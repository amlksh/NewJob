"""저장소 내 실물 설정(manifest, workflow, gate)이 계약 스키마를 준수하는지 검증."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
PLUGINS = ROOT / "plugins"


def _schema(rel: str) -> dict:
    return json.loads((CONTRACTS / rel).read_text())


@pytest.mark.parametrize("manifest_path",
                         sorted(PLUGINS.glob("*/manifest.yaml")), ids=str)
def test_plugin_manifest_conforms(manifest_path: Path):
    manifest = yaml.safe_load(manifest_path.read_text())
    Draft202012Validator(_schema("manifest/v1/twin-plugin-manifest.schema.json")).validate(manifest)


@pytest.mark.parametrize("workflow_path",
                         sorted(PLUGINS.glob("*/workflows/*/*.yaml")), ids=str)
def test_workflow_conforms(workflow_path: Path):
    workflow = yaml.safe_load(workflow_path.read_text())
    Draft202012Validator(_schema("workflow/v1/workflow.schema.json")).validate(workflow)


@pytest.mark.parametrize("gate_path",
                         sorted(PLUGINS.glob("*/gates/*.yaml")), ids=str)
def test_gate_def_conforms(gate_path: Path):
    gate = yaml.safe_load(gate_path.read_text())
    Draft202012Validator(_schema("gate/v1/gate-def.schema.json")).validate(gate)


def test_manifest_references_exist():
    for manifest_path in PLUGINS.glob("*/manifest.yaml"):
        plugin_dir = manifest_path.parent
        m = yaml.safe_load(manifest_path.read_text())["twin_plugin"]
        for wf in m["workflows"]:
            key, ver = wf.split("/")
            assert (plugin_dir / "workflows" / key / f"{ver}.yaml").exists(), wf
        for gate in m["gates"]:
            assert (plugin_dir / "gates" / f"{gate}.yaml").exists(), gate
