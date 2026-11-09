"""Device ConfigUI: the "Hub zone" menu rebinds a device to a renamed hub zone."""
from unittest.mock import MagicMock

import pytest

import conftest
from conftest import indigo_stub
from test_discovery import FakeDev, Hub, hub, live, respond, stat, temp_of, updates  # noqa: F401


@pytest.fixture
def by_id(hub, monkeypatch):
    """indigo.devices[devId] resolves against the hub list."""
    def getitem(_self, dev_id):
        for d in hub:
            if d.id == dev_id:
                return d
        raise KeyError(dev_id)
    monkeypatch.setattr(type(indigo_stub.devices), "__getitem__", getitem, raising=False)
    return hub


def bound(name, zone=None, **kw):
    return FakeDev(name, 0, props={"zoneName": zone or name}, **kw)


# ------------------------------------------------------------ hubZoneList

def test_zone_list_is_sorted_hub_zones_from_known_zones(plugin):
    plugin._knownZones = frozenset({"Kitchen", "Hall", "Bed"})
    assert plugin.hubZoneList(valuesDict={"zoneName": "Hall"}) == [("Bed", "Bed"), ("Hall", "Hall"), ("Kitchen", "Kitchen")]
    plugin.getNeoData.assert_not_called()  # no hub round-trip while the dialog is open


def test_zone_list_includes_current_zone_missing_from_hub(plugin):
    plugin._knownZones = frozenset({"Hall", "New"})
    assert plugin.hubZoneList(valuesDict={"zoneName": "Old"}) == [
        ("Hall", "Hall"), ("New", "New"), ("Old", "Old (not on hub)")]


def test_zone_list_without_values_dict(plugin):
    plugin._knownZones = frozenset({"Hall"})
    assert plugin.hubZoneList() == [("Hall", "Hall")]
    assert plugin.hubZoneList(valuesDict=None, typeId="heatmiserNeostat", targetId=0) == [("Hall", "Hall")]


def test_empty_known_zones_fetches_live_data_once(plugin):
    plugin.neohubGen2 = True
    plugin.getNeoData.return_value = live([stat("Zed"), stat("Alpha")])
    assert plugin.hubZoneList(valuesDict={"zoneName": "Alpha"}) == [("Alpha", "Alpha"), ("Zed", "Zed")]
    plugin.getNeoData.assert_called_once_with('"GET_LIVE_DATA":0')


def test_empty_known_zones_gen1_asks_for_info(plugin):
    plugin.getNeoData.return_value = live([stat("Alpha")])
    plugin.hubZoneList(valuesDict={"zoneName": "Alpha"})
    plugin.getNeoData.assert_called_once_with('"INFO":0')


@pytest.mark.parametrize("reply", ["", {"result": "ok"}, None])
def test_failed_fetch_still_returns_current_zone(plugin, reply):
    plugin.getNeoData.return_value = reply
    assert plugin.hubZoneList(valuesDict={"zoneName": "Old"}) == [("Old", "Old (not on hub)")]
    plugin.logger.debug.assert_called()


def test_exception_is_logged_and_current_zone_returned(plugin):
    plugin.getNeoData.side_effect = RuntimeError("boom")
    assert plugin.hubZoneList(valuesDict={"zoneName": "Old"}) == [("Old", "Old (not on hub)")]
    plugin.logger.exception.assert_called_once()


def test_exception_with_no_current_zone_returns_empty_list(plugin):
    plugin.getNeoData.side_effect = RuntimeError("boom")
    assert plugin.hubZoneList() == []


# ------------------------------------------------------------ validation

def test_validation_rejects_empty_zone(plugin, by_id):
    by_id.append(bound("Hall"))
    for empty in ("", None):
        ok, vals, errs = plugin.validateDeviceConfigUi({"zoneName": empty}, "heatmiserNeostat", by_id[0].id)
        assert ok is False
        assert "zoneName" in errs and "showAlertText" in errs
        assert type(errs) is indigo_stub.Dict  # never a plain dict


def test_validation_rejects_zone_claimed_by_another_live_device(plugin, by_id):
    hall, new = bound("Hall"), bound("New Heatmiser", "New")
    by_id += [hall, new]
    ok, vals, errs = plugin.validateDeviceConfigUi({"zoneName": "New"}, "heatmiserNeostat", hall.id)
    assert ok is False
    assert "'New'" in errs["zoneName"] and "'New Heatmiser'" in errs["zoneName"] and "SUPERSEDED" in errs["zoneName"]
    assert errs["showAlertText"]
    assert type(errs) is indigo_stub.Dict
    assert hall.id not in plugin._pendingRebind


def test_validation_accepts_own_zone(plugin, by_id):
    hall = bound("Hall")
    by_id.append(hall)
    assert plugin.validateDeviceConfigUi({"zoneName": "Hall"}, "heatmiserNeostat", hall.id) == (True, {"zoneName": "Hall"})
    assert plugin._pendingRebind == {}  # unchanged zone: nothing to rebind


def test_validation_ignores_superseded_device_claim(plugin, by_id):
    hall, old = bound("Hall"), bound("Old SUPERSEDED", "Old")
    by_id += [hall, old]
    ok, _ = plugin.validateDeviceConfigUi({"zoneName": "Old"}, "heatmiserNeostat", hall.id)[:2]
    assert ok is True


def test_validation_accepts_unclaimed_zone_and_stashes_old_and_new(plugin, by_id):
    hall = bound("Hall")
    by_id.append(hall)
    plugin._knownZones = frozenset({"Hall", "Lounge"})
    assert plugin.validateDeviceConfigUi({"zoneName": "Lounge"}, "heatmiserNeostat", hall.id)[0] is True
    assert plugin._pendingRebind == {hall.id: ("Hall", "Lounge")}


def test_validation_accepts_zone_not_on_hub(plugin, by_id):
    hall = bound("Hall")
    by_id.append(hall)
    plugin._knownZones = frozenset({"Hall"})  # hub may be unreachable; the poll loop flags a missing zone
    assert plugin.validateDeviceConfigUi({"zoneName": "Ghost"}, "heatmiserNeostat", hall.id)[0] is True
    assert plugin._pendingRebind == {hall.id: ("Hall", "Ghost")}


def test_validation_binds_an_unbound_device(plugin, by_id):
    legacy = FakeDev("Hall", 0)
    by_id.append(legacy)
    assert plugin.validateDeviceConfigUi({"zoneName": "Hall"}, "heatmiserNeostat", legacy.id)[0] is True
    assert plugin._pendingRebind == {legacy.id: (None, "Hall")}


def test_failed_revalidation_drops_a_stale_stash(plugin, by_id):
    hall, new = bound("Hall"), bound("New Heatmiser", "New")
    by_id += [hall, new]
    plugin.validateDeviceConfigUi({"zoneName": "Lounge"}, "heatmiserNeostat", hall.id)
    plugin.validateDeviceConfigUi({"zoneName": "Hall"}, "heatmiserNeostat", hall.id)
    assert plugin._pendingRebind == {}


# ------------------------------------------------------------ closedDeviceConfigUi

def test_closed_with_changed_zone_triggers_rediscovery(plugin, by_id):
    hall = bound("Hall")
    by_id.append(hall)
    plugin._missingZonesWarned = {"Hall", "Other"}
    plugin._pendingRebind[hall.id] = ("Hall", "Lounge")
    plugin.closedDeviceConfigUi({"zoneName": "Lounge"}, False, "heatmiserNeostat", hall.id)
    assert plugin._discoveryDone is False
    assert plugin._missingZonesWarned == {"Other"}
    msg = plugin.logger.info.call_args.args[0]
    assert "'Hall'" in msg and "'Lounge'" in msg and "rebound" in msg
    assert plugin._pendingRebind == {}


def test_closed_with_unchanged_zone_leaves_discovery_alone(plugin, by_id):
    hall = bound("Hall")
    by_id.append(hall)
    plugin.closedDeviceConfigUi({"zoneName": "Hall"}, False, "heatmiserNeostat", hall.id)
    assert plugin._discoveryDone is True
    plugin.logger.info.assert_not_called()


def test_closed_when_cancelled_leaves_discovery_alone_and_drops_stash(plugin, by_id):
    hall = bound("Hall")
    by_id.append(hall)
    plugin._pendingRebind[hall.id] = ("Hall", "Lounge")
    plugin.closedDeviceConfigUi({"zoneName": "Lounge"}, True, "heatmiserNeostat", hall.id)
    assert plugin._discoveryDone is True
    assert plugin._pendingRebind == {}  # a stale stash must not fire on a later, unrelated close


# ------------------------------------------------------------ end to end

def test_rename_on_hub_then_rebind_feeds_device_the_new_zone(plugin, by_id):
    """Hub renamed 'Old' to 'New'. Poll one marks the device orphaned; after the rebind the next poll
    runs createDevices and the device reads 'New' with no error state."""
    dev = bound("Old")
    by_id.append(dev)
    plugin._knownZones = frozenset({"New"})  # discovery already saw the hub list with the renamed zone
    # Before the rebind the device is orphaned.
    respond(plugin, live([stat("New")]))
    plugin.updateReadings()
    assert dev.errorState == "ZONE NOT ON HUB"

    # User opens Edit Device, picks 'New' (the new auto-created device does not exist in this scenario).
    ok = plugin.validateDeviceConfigUi({"zoneName": "New"}, "heatmiserNeostat", dev.id)[0]
    assert ok is True
    dev.pluginProps["zoneName"] = "New"  # Indigo saves the props after validation succeeds
    plugin.closedDeviceConfigUi({"zoneName": "New"}, False, "heatmiserNeostat", dev.id)
    assert plugin._discoveryDone is False

    plugin.neohubGen2 = False
    # updateStatState is mocked by the hub fixture; the real one clears the error state through
    # updateStatesOnServer(clearErrorState=True) / updateStateOnServer(clearErrorState=True).
    plugin.updateStatState.side_effect = lambda rep, index, d: setattr(d, "errorState", None)
    plugin.updateReadings()  # runs createDevices() instead of the per-device loop
    assert plugin._discoveryDone is True
    assert dev.pluginProps["zoneName"] == "New"
    assert dev.errorState is None
    plugin.updateStatState.assert_called_once()
    args = plugin.updateStatState.call_args.args
    assert args[2] is dev and args[0]["devices"][args[1]]["ZONE_NAME"] == "New"
    assert args[0]["devices"][args[1]]["ACTUAL_TEMP"] == temp_of("New")
