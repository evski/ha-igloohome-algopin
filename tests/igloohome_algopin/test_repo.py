"""Repository shape for the standalone HACS integration."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "custom_components" / "igloohome_algopin"


def test_manifest_pins_the_verified_package_and_matches_the_version_constant():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    assert manifest["domain"] == "igloohome_algopin"
    assert manifest["name"] == "Igloo AlgoPIN"
    assert manifest["requirements"] == ["igloohome-api==0.1.2"]
    assert manifest["version"] == "0.1.1"
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "service"
    assert manifest["codeowners"] == ["@evski"]
    assert manifest["documentation"] == "https://github.com/evski/ha-igloohome-algopin"
    assert manifest["issue_tracker"] == "https://github.com/evski/ha-igloohome-algopin/issues"
    source = (COMPONENT / "const.py").read_text()
    assert 'VERSION = "0.1.1"' in source
    assert "igloohome-api==0.1.2" in source


def test_hacs_metadata_and_validation_workflow():
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert hacs["name"] == "Igloo AlgoPIN"
    assert hacs["render_readme"] is True
    assert "country" not in hacs
    workflow = (ROOT / ".github" / "workflows" / "validate.yaml").read_text()
    assert "home-assistant/actions/hassfest@master" in workflow
    assert "hacs/action@main" in workflow
    assert "category: integration" in workflow
    assert "pytest" in workflow
    assert "ignore:" not in workflow
    assert "ignore " not in workflow
    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert "## 0.1.1" in changelog
    readme = (ROOT / "README.md").read_text()
    assert "/config/custom_components" in readme
    assert "Custom repositories" in readme
    assert "individual" in readme.lower()
    assert "create_hourly_algopin" in readme
    assert "create_daily_algopin" in readme
    assert "revoke_algopin" in readme
    assert "website_pin_link" in readme or "Website PIN link" in readme
    assert "door_codes" in readme or "Door codes" in readme
    assert "api_access_ends" in readme or "API access ends" in readme
    assert "after the Validate workflow on that commit has succeeded" in readme
    assert (ROOT / "LICENSE").is_file()
    assert "Copyright (c) 2026 evski" in (ROOT / "LICENSE").read_text()


def test_sensors_are_the_deployed_set():
    sensor = (COMPONENT / "sensor.py").read_text()
    assert "website_pin_link" in sensor
    assert "door_codes" in sensor
    assert "api_access_ends" in sensor
    assert "api_status" not in sensor
    assert '"markdown"' in sensor
    strings = json.loads((COMPONENT / "strings.json").read_text())
    assert set(strings["entity"]["sensor"]) == {"website_pin_link", "door_codes", "api_access_ends"}
    assert "api_status" not in json.dumps(strings)
    english = json.loads((COMPONENT / "translations" / "en.json").read_text())
    assert english == strings
    assert "create_hourly_algopin" in strings["services"]
    assert "create_daily_algopin" in strings["services"]
    assert "revoke_algopin" in strings["services"]


def test_component_does_not_persist_service_pins_or_fire_events():
    text = "\n".join(path.read_text() for path in COMPONENT.glob("*.py"))
    assert "helpers.storage" not in text
    assert "async_fire(" not in text
    assert "SupportsResponse.ONLY" in text
    assert "async_add_executor_job" not in text
    assert "accessType" in text


def test_setup_discovers_support_pins_and_does_not_create_a_pin():
    flow = (COMPONENT / "config_flow.py").read_text()
    assert "list_algopin_devices" in flow
    assert "create_hourly" not in flow
    assert "create_daily" not in flow
    assert "/algopin/" not in flow
    assert "homeId" not in flow
    assert "batteryLevel" not in flow
    assert "CONF_WEBSITE_STATUS_URL" in flow
    sensor = (COMPONENT / "sensor.py").read_text()
    assert "entity_locks" in sensor
    assert "battery" not in sensor.lower()


def test_single_integration_package_has_no_personal_data():
    packages = [
        path.name
        for path in (ROOT / "custom_components").iterdir()
        if path.is_dir() and not path.name.startswith("__")
    ]
    assert packages == ["igloohome_algopin"]
    banned = ("IGB403fe" + "3b9d", "app" + "le", "iph" + "one", "ip" + "ad")
    checked = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix not in {".py", ".md", ".json", ".yaml", ".yml", ".txt"}:
            continue
        checked.append(path.relative_to(ROOT).as_posix().lower())
        text = path.read_text().lower()
        for word in banned:
            assert word not in text, f"{word} in {path}"
    assert checked
