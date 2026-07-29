from __future__ import annotations

import json
import py_compile
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_committed_asset_outputs_and_manifest_exist() -> None:
    css = ROOT / "static/css/app.css"
    renderer = ROOT / "static/js/cornerstone-renderer.js"
    manifest = json.loads((ROOT / "assets/vendor/manifest.json").read_text(encoding="utf-8"))

    assert css.is_file() and css.stat().st_size > 0
    assert renderer.is_file() and renderer.stat().st_size > 0
    assert "LumoraCornerstone" in renderer.read_text(encoding="utf-8")
    assert "dicom-parser" not in renderer.read_text(encoding="utf-8")
    assert {item["name"] for item in manifest["dependencies"]} >= {
        "@cornerstonejs/core",
        "tailwindcss",
        "htmx.org",
        "alpinejs",
        "chart.js",
        "tabulator-tables",
    }
    assert {item["path"] for item in manifest["vendored"]} == {
        "assets/vendor/htmx.min.js",
        "assets/vendor/alpine.min.js",
        "assets/vendor/chart.umd.min.js",
        "assets/vendor/tabulator.min.js",
        "assets/vendor/tabulator.min.css",
    }


def test_asset_check_script_is_valid_python() -> None:
    py_compile.compile(str(ROOT / "scripts/check-assets.py"), doraise=True)
