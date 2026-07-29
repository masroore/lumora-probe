from __future__ import annotations

from pathlib import Path

import pytest

from lumora_probe.core.config import ConfigSource, StartupConfig, load_startup_config
from lumora_probe.core.errors import (
    ConfigurationError,
    LifecycleError,
    NetworkExposureError,
    NetworkFilesystemError,
    PathSecurityError,
    RestartRequiredError,
    SettingLockedError,
    VersionMismatchError,
)
from lumora_probe.core.health import HealthRegistry
from lumora_probe.core.lifecycle import ExecutorPool, LifecycleManager, ServiceHealth
from lumora_probe.core.paths import (
    DataPaths,
    assert_local_filesystem,
    ensure_version_marker,
    resolve_capture_path,
)
from lumora_probe.settings.runtime import RuntimeSettingsStore, SettingSource


def test_startup_config_precedence_and_provenance(tmp_path: Path) -> None:
    (tmp_path / "lumora.toml").write_text(
        'port = 8010\nbind_host = "127.0.0.1"\n', encoding="utf-8"
    )
    (tmp_path / ".env").write_text("LUMORA_PORT=8020\n", encoding="utf-8")

    config, sources = load_startup_config(
        environ={"LUMORA_DATA_DIR": str(tmp_path / "data"), "LUMORA_PORT": "8030"}, cwd=tmp_path
    )

    assert config.port == 8030
    assert config.data_dir == tmp_path / "data"
    assert sources["port"] is ConfigSource.ENV
    assert sources["bind_host"] is ConfigSource.FILE
    assert sources["executor_workers"] is ConfigSource.DEFAULT


def test_startup_config_validation_names_key_and_source(tmp_path: Path) -> None:
    (tmp_path / "lumora.toml").write_text('port = "not-a-port"\n', encoding="utf-8")

    with pytest.raises(ConfigurationError) as raised:
        load_startup_config(environ={"LUMORA_DATA_DIR": str(tmp_path / "data")}, cwd=tmp_path)

    assert raised.value.context["key"] == "port"
    assert raised.value.context["source"] == "file"
    assert "port" in raised.value.message


def test_non_loopback_bind_requires_acknowledgment(tmp_path: Path) -> None:
    with pytest.raises(NetworkExposureError) as raised:
        load_startup_config(
            environ={
                "LUMORA_DATA_DIR": str(tmp_path / "data"),
                "LUMORA_BIND_HOST": "0.0.0.0",
            },
            cwd=tmp_path,
        )

    assert "acknowledgment" in raised.value.message

    config, _ = load_startup_config(
        environ={
            "LUMORA_DATA_DIR": str(tmp_path / "data"),
            "LUMORA_BIND_HOST": "0.0.0.0",
            "LUMORA_ALLOW_UNAUTHENTICATED_NETWORK": "true",
        },
        cwd=tmp_path,
    )
    assert config.bind_host == "0.0.0.0"


def test_data_paths_initialise_and_refuse_network_sqlite(tmp_path: Path) -> None:
    config = StartupConfig(data_dir=tmp_path / "data")
    paths = DataPaths.from_config(config)
    paths.initialise(network_detector=lambda _: False)
    assert paths.settings_file.parent == paths.root
    assert paths.version_file.read_text(encoding="utf-8").strip() == "1"

    with pytest.raises(NetworkFilesystemError):
        assert_local_filesystem((paths.index_db,), detector=lambda _: True)


def test_capture_path_rejects_traversal_and_non_uuid7(tmp_path: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_capture_path("../../etc", allowed_root=tmp_path)
    with pytest.raises(PathSecurityError):
        resolve_capture_path("018f0c40-7d3d-6abc-8d2e-5b5a58fce0b5", allowed_root=tmp_path)

    capture_id = "018f0c40-7d3d-7abc-8d2e-5b5a58fce0b5"
    path = resolve_capture_path(capture_id, allowed_root=tmp_path, filename="events.jsonl")
    assert path == (tmp_path / capture_id / "events.jsonl").resolve()


def test_newer_data_directory_version_is_not_mangled(tmp_path: Path) -> None:
    marker = tmp_path / "version"
    marker.write_text("99\n", encoding="utf-8")
    with pytest.raises(VersionMismatchError):
        ensure_version_marker(marker)
    assert marker.read_text(encoding="utf-8") == "99\n"


def test_runtime_settings_are_separate_and_persist_with_provenance(tmp_path: Path) -> None:
    store = RuntimeSettingsStore(tmp_path / "settings.toml")
    assert store.snapshot("ring_buffer_seconds").source == SettingSource.DEFAULT
    updated = store.update("ring_buffer_seconds", 600)
    assert updated.value == 600
    assert updated.source == SettingSource.RUNTIME
    assert (tmp_path / "settings.toml").is_file()

    reloaded = RuntimeSettingsStore(tmp_path / "settings.toml")
    assert reloaded.snapshot("ring_buffer_seconds").value == 600
    assert reloaded.snapshot("ring_buffer_seconds").source == SettingSource.FILE

    locked = RuntimeSettingsStore(tmp_path / "settings.toml", environ={"LUMORA_THEME": "dark"})
    assert locked.snapshot("theme").source == SettingSource.ENV
    with pytest.raises(SettingLockedError):
        locked.update("theme", "light")
    with pytest.raises(RestartRequiredError):
        store.update("bind_host", "127.0.0.1")


class _FakeService:
    def __init__(self, name: str, calls: list[str], *, fail_start: bool = False) -> None:
        self.name = name
        self.calls = calls
        self.fail_start = fail_start
        self.started = False

    async def start(self) -> None:
        self.calls.append(f"start:{self.name}")
        if self.fail_start:
            raise RuntimeError("boom")
        self.started = True

    async def stop_accepting(self) -> None:
        self.calls.append(f"stop_accepting:{self.name}")

    async def drain(self) -> None:
        self.calls.append(f"drain:{self.name}")

    async def flush(self) -> None:
        self.calls.append(f"flush:{self.name}")

    async def stop(self) -> None:
        self.calls.append(f"stop:{self.name}")
        self.started = False

    async def health(self) -> ServiceHealth:
        return ServiceHealth(self.name, self.started, True)


@pytest.mark.asyncio
async def test_lifecycle_starts_in_order_and_drains_in_reverse() -> None:
    calls: list[str] = []
    first = _FakeService("first", calls)
    second = _FakeService("second", calls)
    manager = LifecycleManager(shutdown_grace_seconds=1)
    manager.register(first)
    manager.register(second)

    await manager.start()
    assert manager.state.value == "running"
    await manager.shutdown()
    assert manager.state.value == "stopped"
    assert calls == [
        "start:first",
        "start:second",
        "stop_accepting:first",
        "stop_accepting:second",
        "drain:first",
        "drain:second",
        "flush:first",
        "flush:second",
        "stop:second",
        "stop:first",
    ]


@pytest.mark.asyncio
async def test_lifecycle_start_failure_stops_started_services() -> None:
    calls: list[str] = []
    manager = LifecycleManager()
    manager.register(_FakeService("first", calls))
    manager.register(_FakeService("second", calls, fail_start=True))

    with pytest.raises(LifecycleError):
        await manager.start()
    assert calls == ["start:first", "start:second", "stop:first"]


@pytest.mark.asyncio
async def test_executor_pool_keeps_blocking_work_off_loop() -> None:
    pool = ExecutorPool(1)
    assert await pool.run(lambda value: value + 1, 41) == 42
    await pool.shutdown()


@pytest.mark.asyncio
async def test_health_registry_distinguishes_readiness_and_liveness() -> None:
    registry = HealthRegistry()
    registry.register(
        "api", lambda: ServiceHealth("api", ready=False, alive=True, detail="warming")
    )
    report = await registry.check()
    assert report.ready is False
    assert report.alive is True
    assert report.as_dict()["services"][0]["detail"] == "warming"


def test_structured_error_serializes_context() -> None:
    error = ConfigurationError(
        code="LUMORA-CORE-TEST-001",
        message="invalid setting",
        remediation="fix it",
        context={"token": "secret", "key": "port"},
    )
    assert error.as_dict()["context"]["key"] == "port"
    assert "invalid setting" in str(error)


def test_logging_redacts_sensitive_values() -> None:
    from lumora_probe.core.logging import redact_sensitive

    result = redact_sensitive(None, "info", {"password": "secret", "nested": {"token": "x"}})
    assert result["password"] == "[REDACTED]"
    assert result["nested"] == {"token": "[REDACTED]"}
