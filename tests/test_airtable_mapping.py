"""Airtable serialization + schema generation — no network required."""

import json

from creative_director.domain.models import Asset, Project, Version, Workspace
from creative_director.repositories.airtable.mapping import (
    from_fields,
    json_field_names,
    to_fields,
)
from creative_director.repositories.airtable.schema import TABLE_BY_MODEL_KEY, TABLES


def test_json_fields_detected_from_annotations():
    assert "brand_config" in json_field_names(Workspace)
    assert "target_modalities" in json_field_names(Project)
    assert "spec" in json_field_names(Asset)
    assert "name" not in json_field_names(Workspace)


def test_dict_and_list_fields_are_json_encoded():
    proj = Project(
        workspace_id="w1",
        name="Launch",
        goal="Ship it",
        constraints={"tone": "bold"},
        target_modalities=["image", "copy"],
    )
    fields = to_fields(proj)
    assert fields["constraints"] == json.dumps({"tone": "bold"})
    assert json.loads(fields["target_modalities"]) == ["image", "copy"]
    # None fields are omitted from the payload.
    assert "output_ref" not in fields


def test_round_trip_preserves_entity():
    version = Version(
        workspace_id="w1",
        asset_id="a1",
        provider="openai",
        prompt="a red bicycle",
        params={"size": "1024x1024"},
        parent_version_id="v0",
        critique={"score": 0.8, "notes": "good"},
    )
    restored = from_fields(Version, to_fields(version))
    assert restored.id == version.id
    assert restored.params == {"size": "1024x1024"}
    assert restored.critique["score"] == 0.8
    assert restored.parent_version_id == "v0"
    assert restored.provider == "openai"


def test_schema_covers_every_model_and_id_is_primary():
    for key in ("workspaces", "projects", "assets", "versions", "pipeline_runs"):
        assert key in TABLE_BY_MODEL_KEY
    for table in TABLES:
        # First field must be the primary key: our UUID `id`.
        assert table.fields[0].name == "id"


def test_enum_fields_become_single_selects_with_choices():
    workspaces = TABLE_BY_MODEL_KEY["workspaces"]
    kind = next(f for f in workspaces.fields if f.name == "kind")
    assert kind.type == "singleSelect"
    choice_names = {c["name"] for c in kind.options["choices"]}
    assert choice_names == {"personal", "client"}
