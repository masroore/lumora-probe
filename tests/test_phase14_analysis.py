"""Phase 14 condition ID registry tests."""

from __future__ import annotations

import pytest

from lumora_probe.analysis.contracts import (
    ConditionDefinition,
    ConditionId,
    ConditionIdRegistry,
)
from lumora_probe.shared.errors import DomainInvariantError

pytestmark = pytest.mark.unit


def _definition(condition_id: str, name: str = "No presentation context") -> ConditionDefinition:
    return ConditionDefinition(
        condition_id=condition_id,
        name=name,
        description="No acceptable presentation context was negotiated.",
        remediation="Review the offered SOP class and transfer syntax contexts.",
    )


def test_condition_id_validates_and_formats_parts() -> None:
    condition_id = ConditionId.from_parts("NEG", 4)

    assert condition_id.value == "LP-NEG-004"
    assert str(condition_id) == "LP-NEG-004"
    assert ConditionId("LP-NEG-004") == condition_id


@pytest.mark.parametrize(
    "value",
    ["LP-NEG-4", "LP-neg-004", "LP-NEGO-004", "NEG-004", "LP-NEG-000", "LP-NEG-1000"],
)
def test_condition_id_rejects_invalid_values(value: str) -> None:
    with pytest.raises(DomainInvariantError):
        ConditionId(value)


def test_condition_id_registry_rejects_reuse_and_orders_entries() -> None:
    registry = ConditionIdRegistry(
        (
            _definition("LP-TRN-002", "Transfer syntax mismatch"),
            _definition("LP-NEG-004"),
        )
    )

    assert registry.ids() == (ConditionId("LP-NEG-004"), ConditionId("LP-TRN-002"))
    assert registry.require("LP-NEG-004").name == "No presentation context"
    assert registry.get("LP-UNK-001") is None
    assert len(registry) == 2

    with pytest.raises(DomainInvariantError, match="already registered"):
        registry.register(_definition("LP-NEG-004", "Renamed condition"))


def test_condition_definition_normalizes_text_and_registry_contains_only_typed_ids() -> None:
    definition = ConditionDefinition(
        condition_id="LP-NEG-004",
        name="  No presentation context  ",
        description="  observed fact  ",
        remediation="  inspect negotiation  ",
    )
    registry = ConditionIdRegistry([definition])

    assert definition.name == "No presentation context"
    assert definition.description == "observed fact"
    assert definition.remediation == "inspect negotiation"
    assert ConditionId("LP-NEG-004") in registry
    assert "LP-NEG-004" not in registry
