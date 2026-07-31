"""Example analyzer using only the public Lumora Probe plugin SDK."""

from __future__ import annotations

from lumora_probe.plugins.api import hookimpl
from lumora_probe.plugins.contracts import AnalysisContextDTO, FindingDTO


class ExamplePlugin:
    """Report an explicit marker from observed evidence."""

    @hookimpl
    def analyze(self, context: AnalysisContextDTO) -> tuple[FindingDTO, ...]:
        findings: list[FindingDTO] = []
        for event in context.events:
            if event.event_name != "ExampleMarker" or event.sequence is None:
                continue
            findings.append(
                FindingDTO(
                    rule_id="EXAMPLE-RULE-001",
                    rule_version="1",
                    rule_set_version="example-v1",
                    confidence="certain",
                    cited_sequences=(event.sequence,),
                    explanation="The example marker was observed in the event stream.",
                    next_steps=("Inspect the cited event and remove the marker when resolved.",),
                )
            )
        return tuple(findings)


plugin = ExamplePlugin()
