"""Public contracts boundary for the ``analysis`` slice."""

from __future__ import annotations

from . import domain as _domain

ConditionDefinition = _domain.ConditionDefinition
ConditionId = _domain.ConditionId
ConditionIdRegistry = _domain.ConditionIdRegistry
ConditionRegistry = _domain.ConditionRegistry

__all__: tuple[str, ...] = ()
