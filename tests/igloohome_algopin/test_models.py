"""Prefix check. IGB4 is on the docs table. A retail name is not a device id."""

from custom_components.igloohome_algopin.models import (
    classify_algopin,
    device_label,
    is_offered,
    lookup_model,
)


def test_igb4_on_the_table_is_deadbolt_2s_and_algopin_yes():
    info = lookup_model("IGB4test")
    assert info is not None
    assert info.prefix == "IGB4"
    assert info.name == "Deadbolt 2S Metal Grey"
    assert info.algopin is True
    assert info.kind == "lock"
    assert classify_algopin("IGB4test", "Lock") == "allow"
    assert is_offered("IGB4test", "Lock") is True
    label = device_label("42battery", "IGB4test", "Lock")
    assert "IGB4test" in label
    assert "42battery" in label
    assert "prefix IGB4" in label
    assert "Deadbolt" not in label


def test_igb4_prefix_is_allowed_without_naming_a_product():
    metal = lookup_model("IGB4example")
    assert metal is not None
    assert metal.prefix == "IGB4"
    assert metal.algopin is True
    assert classify_algopin("IGB4example", "Lock") == "allow"
    label = device_label("Front door", "IGB4example", "Lock")
    assert "IGB4example" in label
    assert "prefix IGB4" in label
    assert "Deadbolt" not in label
    assert "Smart Deadbolt" not in label


def test_retail_name_is_not_a_device_and_is_not_compatible():
    assert lookup_model("Smart Deadbolt 4 Metal Grey") is None
    assert classify_algopin("Smart Deadbolt 4 Metal Grey", "") == "unconfirmed"
    label = device_label("Front door", "SmartDeadbolt4", "")
    assert "Deadbolt 2S" not in label
    assert "not a published prefix" in label


def test_retrofit_and_bridge_type_are_denied_from_real_fields():
    retrofit = lookup_model("OE1Xexample")
    assert retrofit is not None
    assert retrofit.algopin is False
    assert classify_algopin("OE1Xexample", "Lock") == "deny"
    assert classify_algopin("IGB4example", "Bridge") == "deny"
    assert classify_algopin("IEF1example", "Fob") == "deny"


def test_unknown_prefix_stays_unconfirmed_and_has_no_model():
    assert lookup_model("ZZZZexample") is None
    assert classify_algopin("ZZZZexample", "Lock") == "unconfirmed"
    assert classify_algopin("ZZZZexample", "") == "unconfirmed"
    label = device_label("Front door", "ZZZZexample", "Lock")
    assert "not a published prefix" in label
    assert "igloohome account" in label


def test_longer_prefix_wins_for_the_table_check_only():
    assert lookup_model("IGB4Aexample").prefix == "IGB4A"
    assert lookup_model("IGB4example").prefix == "IGB4"
    assert classify_algopin("IGB4Aexample", "Lock") == "allow"


def test_bridge_prefixes():
    assert lookup_model("EB1Xexample").kind == "bridge"
    assert lookup_model("EB2Xexample").name == "Bridge 2"
    assert classify_algopin("EB1Xexample", "Bridge") == "deny"
    assert classify_algopin("EB1Xexample", "") == "deny"
