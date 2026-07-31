"""Phase 18 security gap coverage for validation, containment, and redaction."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from lumora_probe.core.errors import PathSecurityError
from lumora_probe.core.logging import redact_sensitive
from lumora_probe.core.paths import assert_contained, resolve_capture_path
from lumora_probe.plugins.repository import PluginRepository
from lumora_probe.settings.runtime import RuntimeSettings, _redact_setting_value
from lumora_probe.web.api import create_app


@pytest.mark.component
@pytest.mark.asyncio
async def test_search_rejects_invalid_kinds_and_oversized_query() -> None:
    application = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://localhost"
    ) as client:
        search = await client.get("/api/v1/search", params={"kinds": "not-a-kind"})
        oversized = await client.get("/api/v1/search", params={"q": "x" * 300})

    assert search.status_code == 400
    assert oversized.status_code == 422


@pytest.mark.unit
def test_runtime_theme_accepts_high_contrast_and_rejects_unknown() -> None:
    assert RuntimeSettings(theme="high-contrast").theme == "high-contrast"
    with pytest.raises(ValidationError):
        RuntimeSettings(theme="neon")


@pytest.mark.component
def test_path_sinks_reject_traversal_and_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "captures"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    capture_id = "018f0d4e-7b6a-7000-8000-000000001801"

    with pytest.raises(PathSecurityError):
        resolve_capture_path("../escape", allowed_root=root)
    with pytest.raises(PathSecurityError):
        assert_contained(outside, root)

    capture_dir = resolve_capture_path(capture_id, allowed_root=root)
    capture_dir.mkdir()
    link = capture_dir / "escape"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(PathSecurityError):
        assert_contained(link, root)

    plugins_root = tmp_path / "plugins"
    plugins_root.mkdir()
    repository = PluginRepository(plugins_root)
    with pytest.raises(ValueError, match="direct child"):
        repository.read_manifest(tmp_path / "elsewhere")


@pytest.mark.unit
def test_secret_redaction_covers_credential_shaped_keys() -> None:
    redacted = redact_sensitive(
        None,
        "info",
        {
            "api_key": "k",
            "client_secret": "s",
            "nested": {"refresh_token": "r", "certificate": "cert"},
            "safe": "ok",
        },
    )
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["client_secret"] == "[REDACTED]"
    assert redacted["nested"]["refresh_token"] == "[REDACTED]"
    assert redacted["nested"]["certificate"] == "[REDACTED]"
    assert redacted["safe"] == "ok"
    assert _redact_setting_value("access_key", "value") == "[REDACTED]"
    assert _redact_setting_value("tls_certificate", "value") == "[REDACTED]"
    assert _redact_setting_value("theme", "dark") == "dark"
