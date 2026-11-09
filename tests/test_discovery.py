"""Device discovery and polling match on the hub's ZONE_NAME, not list position.

Regression tests for issue #33: removing a stat from the NeoHub shifts
every later device up one slot, and address-based matching silently fed
each Indigo device its neighbour's readings.
"""
import zlib
from unittest.mock import MagicMock

import pytest

import conftest


class FakeDev:
    def __init__(self, name, address, typeId="heatmiserNeostat", props=None):
        self.name = name
        self.address = address
        self.deviceTypeId = typeId
        self.pluginProps = dict(props or {})
        self.id = hash(name) & 0xFFFF
        self.replaced = False
        self.errorState = None
        self.updateStateOnServer = MagicMock()
        self.updateStatesOnServer = MagicMock()
        self.updateStateImageOnServer = MagicMock()

    def replacePluginPropsOnServer(self, props):
        self.pluginProps = dict(props)

    def replaceOnServer(self):
        self.replaced = True

    def setErrorStateOnServer(self, text):
        self.errorState = text


def temp_of(name):
    """A per-zone distinct temperature, so a reading fed to the wrong zone is detectable."""
    return 10 + (zlib.crc32(name.encode()) % 1000) / 10


def stat(name, **extra):
    d = {"ZONE_NAME": name, "DEVICE_TYPE": 1, "ACTUAL_TEMP": temp_of(name), "SET_TEMP": 21}
    d.update(extra)
    return d


def live(devices, **hub):
    rep = {"devices": devices}
    rep.update(hub)
    return rep


def fake_create(**kw):
    return FakeDev(kw["name"], kw["address"], kw["deviceTypeId"], kw["props"])


class Hub(list):
    """The plugin's Indigo devices; `taken` holds names owned by other plugins' devices."""

    def __init__(self):
        super().__init__()
        self.taken = set()


@pytest.fixture
def hub(plugin, monkeypatch):
    """Wire indigo.devices.iter to a mutable list and capture updateStatState calls."""
    devs = Hub()
    monkeypatch.setattr(conftest.indigo_stub.devices, "iter", MagicMock(side_effect=lambda *_: list(devs)))
    # `name in indigo.devices` is how the plugin detects a name clash before creating.
    monkeypatch.setattr(type(conftest.indigo_stub.devices), "__contains__",
                        lambda _self, name: name in devs.taken or any(d.name == name for d in devs), raising=False)
    monkeypatch.setattr(conftest.indigo_stub.device, "create", MagicMock(side_effect=fake_create))
    plugin.updateStatState = MagicMock()
    plugin.updateStatState.side_effect = None
    return devs


def respond(plugin, rep, known=()):
    """Stub the hub response and mark its zones (plus `known`) as already discovered, so a poll
    exercises the per-device path instead of triggering new-zone rediscovery."""
    plugin.getNeoData.return_value = rep
    plugin._knownZones = frozenset(e.get("ZONE_NAME", e.get("device")) for e in rep["devices"]) | frozenset(known)


def _zone_of(entry):
    return entry.get("ZONE_NAME", entry.get("device"))


def updates(plugin):
    """[(device name, zone name of the response entry it was fed)] in call order."""
    return [(c.args[2].name, _zone_of(c.args[0]["devices"][c.args[1]])) for c in plugin.updateStatState.call_args_list]


def updates_by_index(plugin):
    """{device name: hub list index it was fed}."""
    return {c.args[2].name: c.args[1] for c in plugin.updateStatState.call_args_list}


# ---------------------------------------------------------------- polling

def test_removing_middle_device_keeps_every_reading_on_its_own_zone(plugin, hub):
    # Devices were created when Toilet was at 11 and Kitchen at 12; Ensuite (10) has since been removed.
    hub += [
        FakeDev("Hall", 9, props={"zoneName": "Hall"}),
        FakeDev("Toilet", 11, props={"zoneName": "Toilet"}),
        FakeDev("Kitchen", 12, props={"zoneName": "Kitchen"}),
    ]
    respond(plugin, live([stat("Hall"), stat("Toilet"), stat("Kitchen")]))
    plugin.updateReadings()
    assert updates(plugin) == [("Hall", "Hall"), ("Toilet", "Toilet"), ("Kitchen", "Kitchen")]
    # and each was fed its own zone's reading, not a neighbour's
    fed_temps = [(c.args[2].name, c.args[0]["devices"][c.args[1]]["ACTUAL_TEMP"]) for c in plugin.updateStatState.call_args_list]
    assert fed_temps == [(n, temp_of(n)) for n in ("Hall", "Toilet", "Kitchen")]


def test_zone_missing_from_hub_is_warned_not_fed_a_neighbour(plugin, hub):
    hub += [
        FakeDev("Hall", 0, props={"zoneName": "Hall"}),
        FakeDev("Ensuite", 1, props={"zoneName": "Ensuite"}),
    ]
    respond(plugin, live([stat("Hall"), stat("Kitchen")]), known=("Ensuite",))
    plugin.updateReadings()
    plugin.updateReadings()
    assert updates(plugin) == [("Hall", "Hall")] * 2
    assert hub[1].errorState == "ZONE NOT ON HUB"  # the device itself carries the signal, not just the log
    assert sum("Ensuite" in str(c) for c in plugin.logger.warning.call_args_list) == 1  # once, not every poll


def test_zone_that_leaves_returns_and_leaves_again_is_warned_twice(plugin, hub):
    hub += [FakeDev("Hall", 0, props={"zoneName": "Hall"})]
    for devices in ([], [stat("Hall")], []):
        respond(plugin, live(devices), known=("Hall",))
        plugin.updateReadings()
    assert sum("Hall" in str(c) for c in plugin.logger.warning.call_args_list) == 2


def test_duplicate_zone_claim_only_first_device_polled(plugin, hub):
    a = FakeDev("Hall A", 0, props={"zoneName": "Hall"})
    b = FakeDev("Hall B", 0, props={"zoneName": "Hall"})
    hub += [a, b]
    respond(plugin, live([stat("Hall")]))
    plugin.updateReadings()
    assert [c.args[2] for c in plugin.updateStatState.call_args_list] == [a]


def test_startup_hub_failure_then_gen1_poll_still_migrates_legacy_devices(plugin, hub):
    # Gen 1 INFO has no TIMESTAMP_DEVICE_LISTS, so the stamp alone can never trigger rediscovery.
    toilet = FakeDev("Toilet", 3)  # legacy, unbound
    hub.append(toilet)
    plugin.getNeoData.return_value = ""
    plugin._discoveryDone = False
    plugin.createDevices()          # startup: hub unreachable
    assert plugin._discoveryDone is False
    plugin.getNeoData.return_value = {"devices": [{"device": "Toilet", "DEVICE_TYPE": 1}]}
    plugin.updateReadings()         # first good poll
    assert toilet.pluginProps["zoneName"] == "Toilet"
    assert plugin._discoveryDone is True
    assert updates(plugin) == [("Toilet", "Toilet")]


def test_gen1_info_response_matches_on_device_key(plugin, hub):
    hub += [FakeDev("Hall", 5, props={"zoneName": "Hall"})]
    respond(plugin, {"devices": [{"device": "Kitchen", "DEVICE_TYPE": 1}, {"device": "Hall", "DEVICE_TYPE": 1}]})
    plugin.updateReadings()
    assert updates(plugin) == [("Hall", "Hall")]
    assert updates_by_index(plugin) == {"Hall": 1}
    plugin.createDevices()
    conftest.indigo_stub.device.create.assert_called_once()
    assert conftest.indigo_stub.device.create.call_args.kwargs["name"] == "Kitchen"
    assert hub[0].pluginProps["address"] == "1"


def test_two_devices_claiming_one_zone_only_first_updated(plugin, hub):
    a = FakeDev("Hall A", 0, props={"zoneName": "Hall", "neoDeviceType": "1"})
    b = FakeDev("Hall B", 0, props={"zoneName": "Hall", "neoDeviceType": "1"})
    hub += [a, b]
    plugin.getNeoData.return_value = live([stat("Hall")])
    plugin.createDevices()
    assert [c.args[2] for c in plugin.updateStatState.call_args_list] == [a]
    conftest.indigo_stub.device.create.assert_not_called()
    assert any("both claim" in str(c) for c in plugin.logger.warning.call_args_list)


def test_legacy_device_without_zone_name_is_not_matched_by_position(plugin, hub):
    hub += [FakeDev("Toilet", 1)]  # no zoneName prop; address points at Kitchen now
    respond(plugin, live([stat("Hall"), stat("Kitchen"), stat("Toilet")]))
    plugin.updateReadings()
    assert updates(plugin) == []
    plugin.logger.exception.assert_not_called()


def test_device_list_change_triggers_rediscovery(plugin, hub):
    plugin.createDevices = MagicMock()
    plugin._deviceListStamp = 100
    respond(plugin, live([stat("Hall")], TIMESTAMP_DEVICE_LISTS=101))
    plugin.updateReadings()
    plugin.createDevices.assert_called_once()


def test_unchanged_device_list_does_not_rediscover(plugin, hub):
    plugin.createDevices = MagicMock()
    plugin._deviceListStamp = 100
    respond(plugin, live([stat("Hall")], TIMESTAMP_DEVICE_LISTS=100))
    plugin.updateReadings()
    plugin.createDevices.assert_not_called()


# ------------------------------------------------------------- discovery

def test_new_device_at_end_is_created_and_existing_untouched(plugin, hub):
    toilet = FakeDev("Toilet", 0, props={"zoneName": "Toilet", "neoDeviceType": "1"})
    hub.append(toilet)
    plugin.getNeoData.return_value = live([stat("Toilet"), stat("Ensuite")])
    plugin.createDevices()
    create = conftest.indigo_stub.device.create
    create.assert_called_once()
    kw = create.call_args.kwargs
    assert kw["name"] == "Ensuite"
    assert kw["address"] == 1
    assert kw["props"]["zoneName"] == "Ensuite"
    assert toilet.replaced is False
    assert updates(plugin) == [("Toilet", "Toilet"), ("Ensuite", "Ensuite")]
    assert updates_by_index(plugin) == {"Toilet": 0, "Ensuite": 1}


def test_discovery_refreshes_stale_address_to_current_position(plugin, hub):
    kitchen = FakeDev("Kitchen", 12, props={"zoneName": "Kitchen", "neoDeviceType": "1"})
    hub.append(kitchen)
    plugin.getNeoData.return_value = live([stat("Hall"), stat("Kitchen")])
    plugin.createDevices()
    assert kitchen.pluginProps["address"] == "1"  # Indigo migrates this prop to dev.address
    assert kitchen.replaced is False


def test_migration_adopts_zone_when_indigo_name_matches(plugin, hub):
    # Already shifted: Toilet's address points at position 2, but the hub zone "Toilet" is at 1.
    toilet = FakeDev("Toilet", 2)
    towel = FakeDev("Family Bath Towel Rail Heatmiser", 0, typeId="heatmiserNeoTimeclock")
    hub += [toilet, towel]
    plugin.getNeoData.return_value = live([
        stat("Family Bath Towel Rail", TIMECLOCK=True), stat("Toilet"), stat("Kitchen"),
    ])
    plugin.createDevices()
    assert toilet.pluginProps["zoneName"] == "Toilet"
    assert towel.pluginProps["zoneName"] == "Family Bath Towel Rail"
    assert updates(plugin) == [
        ("Family Bath Towel Rail Heatmiser", "Family Bath Towel Rail"), ("Toilet", "Toilet"), ("Kitchen", "Kitchen"),
    ]
    # Kitchen had no device: created, not forced onto the renamed one.
    conftest.indigo_stub.device.create.assert_called_once()
    assert conftest.indigo_stub.device.create.call_args.kwargs["name"] == "Kitchen"


def test_migration_leaves_renamed_device_alone_and_warns(plugin, hub):
    loo = FakeDev("Downstairs Loo", 1)  # renamed in Indigo before upgrading; hub zone is "Toilet"
    hub.append(loo)
    plugin.getNeoData.return_value = live([stat("Hall"), stat("Toilet")])
    plugin.createDevices()
    assert "zoneName" not in loo.pluginProps
    assert loo.replaced is False
    assert loo.errorState == "NO HUB ZONE"
    assert "Downstairs Loo" not in [name for name, _ in updates(plugin)]
    plugin.logger.exception.assert_not_called()
    warned = " ".join(str(c) for c in plugin.logger.warning.call_args_list)
    assert "Downstairs Loo" in warned and "Toilet" in warned
    # Creating "Toilet" now would take the name the user is told to rename to, orphaning their device.
    conftest.indigo_stub.device.create.assert_not_called()
    assert "Not creating devices" in warned


def test_creation_resumes_once_legacy_device_is_renamed_to_zone(plugin, hub):
    loo = FakeDev("Toilet", 1)  # user followed the warning and renamed it; still no zoneName prop
    hub.append(loo)
    plugin.getNeoData.return_value = live([stat("Hall"), stat("Toilet")])
    plugin.createDevices()
    assert loo.pluginProps["zoneName"] == "Toilet"
    conftest.indigo_stub.device.create.assert_called_once()
    assert conftest.indigo_stub.device.create.call_args.kwargs["name"] == "Hall"


def test_hub_host_is_device_bound_to_zone_at_position_zero(plugin, hub):
    stale = FakeDev("Old Hall", 0, props={"zoneName": "Gone Zone"})   # kept stale address 0
    hall = FakeDev("Hall", 7, props={"zoneName": "Hall", "neoDeviceType": "1"})
    hub += [stale, hall]
    plugin.getNeoData.return_value = live([stat("Hall"), stat("Kitchen")])
    plugin.createDevices()
    assert plugin._hubHostDevice() is hall


def test_failed_discovery_response_changes_nothing(plugin, hub):
    dev = FakeDev("Hall", 0, props={"zoneName": "Hall"})
    hub.append(dev)
    plugin._deviceListStamp = 42
    plugin.getNeoData.return_value = ""
    plugin.createDevices()
    conftest.indigo_stub.device.create.assert_not_called()
    assert dev.replaced is False and dev.errorState is None
    assert plugin._deviceListStamp == 42
    plugin.logger.error.assert_called_once()


# ------------------------------------------------- hub unreachable

def test_one_failed_poll_changes_nothing(plugin, hub):
    dev = FakeDev("Hall", 0, props={"zoneName": "Hall"})
    hub.append(dev)
    plugin.getNeoData.return_value = ""
    plugin.updateReadings()
    assert dev.errorState is None
    plugin.updateStatState.assert_not_called()
    plugin.logger.warning.assert_not_called()
    assert plugin._failedPolls == 1


def test_three_failed_polls_flag_every_live_device_and_warn_once(plugin, hub):
    bound = FakeDev("Hall", 0, props={"zoneName": "Hall"})
    unbound = FakeDev("Legacy", 1)
    old = FakeDev("Old SUPERSEDED", 2, props={"zoneName": "Old"})
    hub += [bound, unbound, old]
    plugin.getNeoData.return_value = ""
    for _ in range(3):
        plugin.updateReadings()
    assert bound.errorState == unbound.errorState == "HUB UNREACHABLE"
    assert old.errorState is None
    assert sum("Hub unreachable" in str(c) for c in plugin.logger.warning.call_args_list) == 1
    bound.errorState = None  # something else cleared it; the next failed poll must re-assert
    plugin.updateReadings()
    assert bound.errorState == "HUB UNREACHABLE"
    assert sum("Hub unreachable" in str(c) for c in plugin.logger.warning.call_args_list) == 1
    plugin.updateStatState.assert_not_called()


def test_hub_recovery_clears_error_and_feeds_bound_devices(plugin, hub):
    hall = FakeDev("Hall", 0, props={"zoneName": "Hall"})
    gone = FakeDev("Ensuite", 1, props={"zoneName": "Ensuite"})
    legacy = FakeDev("Legacy", 2)
    hub += [hall, gone, legacy]
    plugin.getNeoData.return_value = ""
    for _ in range(3):
        plugin.updateReadings()
    respond(plugin, live([stat("Hall")]), known=("Ensuite",))
    plugin.updateReadings()
    assert hall.errorState is None                  # cleared and fed
    assert updates(plugin) == [("Hall", "Hall")]
    assert gone.errorState == "ZONE NOT ON HUB"      # cleared, then re-asserted by the poll
    assert legacy.errorState == "NO HUB ZONE"        # unbound: back to its own state, not left HUB UNREACHABLE
    assert plugin._failedPolls == 0
    assert any("Hub reachable again" in str(c) for c in plugin.logger.info.call_args_list)


def test_success_after_fewer_than_three_failures_resets_the_count(plugin, hub):
    hall = FakeDev("Hall", 0, props={"zoneName": "Hall"})
    hub.append(hall)
    plugin.getNeoData.return_value = ""
    plugin.updateReadings()
    plugin.updateReadings()
    respond(plugin, live([stat("Hall")]))
    plugin.updateReadings()
    assert plugin._failedPolls == 0
    assert not any("Hub reachable again" in str(c) for c in plugin.logger.info.call_args_list)
    plugin.getNeoData.return_value = ""
    plugin.updateReadings()
    plugin.updateReadings()
    assert hall.errorState is None  # two fresh failures only


# ------------------------------------------------- new-zone rediscovery

def test_gen1_new_zone_triggers_rediscovery_not_a_poll(plugin, hub):
    hub.append(FakeDev("Hall", 0, props={"zoneName": "Hall"}))
    plugin.createDevices = MagicMock()
    plugin._knownZones = frozenset({"Hall"})
    plugin.getNeoData.return_value = {"devices": [{"device": "Hall", "DEVICE_TYPE": 1}, {"device": "Kitchen", "DEVICE_TYPE": 1}]}
    plugin.updateReadings()
    plugin.createDevices.assert_called_once()
    plugin.updateStatState.assert_not_called()
    assert any("Kitchen" in str(c) for c in plugin.logger.info.call_args_list)


def test_vanished_zone_does_not_rediscover_and_recovers_on_its_own(plugin, hub):
    hall = FakeDev("Hall", 0, props={"zoneName": "Hall"})
    ensuite = FakeDev("Ensuite", 1, props={"zoneName": "Ensuite"})
    hub += [hall, ensuite]
    plugin.createDevices = MagicMock()
    respond(plugin, live([stat("Hall")]), known=("Ensuite",))
    plugin.updateReadings()
    plugin.createDevices.assert_not_called()
    assert ensuite.errorState == "ZONE NOT ON HUB"
    respond(plugin, live([stat("Hall"), stat("Ensuite")]), known=("Ensuite",))
    plugin.updateReadings()
    plugin.createDevices.assert_not_called()
    assert updates(plugin)[-1] == ("Ensuite", "Ensuite")


def test_discovery_then_same_zones_does_not_refetch_but_added_zone_creates_device(plugin, hub, monkeypatch):
    plugin.neohubGen2 = True
    calls = []
    zonesOnHub = [stat("Hall")]

    def hubReply(cmd):
        calls.append(cmd)
        if "GET_ENGINEERS" in cmd:
            return {z["ZONE_NAME"]: {"DEVICE_TYPE": 1} for z in zonesOnHub}
        return live(zonesOnHub)

    def create(**kw):
        dev = fake_create(**kw)
        hub.append(dev)  # the real server would list it from now on
        return dev
    monkeypatch.setattr(conftest.indigo_stub.device, "create", MagicMock(side_effect=create))
    plugin.getNeoData.side_effect = hubReply
    plugin._discoveryDone = False
    plugin.createDevices()
    assert [d.name for d in hub] == ["Hall"]
    assert plugin._knownZones == frozenset({"Hall"})

    calls.clear()
    plugin.updateReadings()                                   # same zones: plain poll
    assert not any("GET_ENGINEERS" in c for c in calls)
    assert len(hub) == 1

    zonesOnHub.append(stat("Kitchen"))
    calls.clear()
    plugin.updateReadings()                                   # new zone: real createDevices runs
    assert any("GET_ENGINEERS" in c for c in calls)
    assert [d.name for d in hub] == ["Hall", "Kitchen"]
    assert plugin._knownZones == frozenset({"Hall", "Kitchen"})


# ------------------------------------------------- hub host must be a neostat

def test_hub_host_is_lowest_address_neostat_when_zone_zero_is_a_plug(plugin, hub):
    plug = FakeDev("Plug", 0, "heatmiserNeoplug", props={"zoneName": "Plug", "neoDeviceType": "6"})
    b = FakeDev("B", 5, props={"zoneName": "B", "neoDeviceType": "1"})
    a = FakeDev("A", 2, props={"zoneName": "A", "neoDeviceType": "1"})
    hub += [plug, b, a]
    plugin.getNeoData.return_value = live([{"ZONE_NAME": "Plug", "DEVICE_TYPE": 6}, stat("A"), stat("B")])
    plugin.createDevices()
    assert plugin._hubHostZone == "Plug"
    assert plugin._hubHostDevice() is a


def test_hub_host_fallback_orders_by_numeric_address_non_numeric_last(plugin, hub):
    plugin._hubHostZone = "Plug"
    plug = FakeDev("Plug", 0, "heatmiserNeoplug", props={"zoneName": "Plug"})
    odd = FakeDev("Odd", "x", props={"zoneName": "Odd"})
    b = FakeDev("B", "10", props={"zoneName": "B"})
    a = FakeDev("A", "2", props={"zoneName": "A"})
    unbound = FakeDev("Unbound", "1")
    hub += [plug, odd, b, a, unbound]
    assert plugin._hubHostDevice() is a
    plugin.logger.debug.assert_called()


def test_hub_host_is_the_zone_zero_neostat_when_there_is_one(plugin, hub):
    plugin._hubHostZone = "Hall"
    low = FakeDev("Low", 0, props={"zoneName": "Low"})
    hall = FakeDev("Hall", 9, props={"zoneName": "Hall"})
    hub += [low, hall]
    assert plugin._hubHostDevice() is hall


def test_hub_host_is_none_without_a_neostat(plugin, hub):
    plugin._hubHostZone = "Plug"
    hub += [FakeDev("Plug", 0, "heatmiserNeoplug", props={"zoneName": "Plug"}),
            FakeDev("Air", 1, "heatmiserNeoSensor", props={"zoneName": "Air"})]
    assert plugin._hubHostDevice() is None


def test_pre_discovery_address_zero_fallback_skips_non_neostats(plugin, hub):
    plugin._discoveryDone = False
    plug = FakeDev("Plug", "0", "heatmiserNeoplug")
    stat0 = FakeDev("Stat", "0")
    hub += [plug, stat0]
    assert plugin._hubHostDevice() is stat0
    hub.remove(stat0)
    assert plugin._hubHostDevice() is None


# ------------------------------------------------- quiet skips are logged

def test_nameless_hub_entry_is_warned_and_ignored(plugin):
    zones = plugin._zonesByName({"devices": [{"ZONE_NAME": "Hall"}, {"DEVICE_TYPE": 1}]})
    assert list(zones) == ["Hall"]
    assert any("entry 1 has no zone name" in str(c) for c in plugin.logger.warning.call_args_list)


def test_duplicate_hub_zone_is_warned_and_first_wins(plugin):
    zones = plugin._zonesByName({"devices": [{"ZONE_NAME": "Hall", "n": 0}, {"ZONE_NAME": "Hall", "n": 1}]})
    assert zones["Hall"] == (0, {"ZONE_NAME": "Hall", "n": 0})
    assert any("'Hall' twice (entries 0 and 1)" in str(c) for c in plugin.logger.warning.call_args_list)


def test_zone_list_warnings_are_not_repeated_every_poll(plugin):
    rep = {"devices": [{"ZONE_NAME": "Hall"}, {"ZONE_NAME": "Hall"}, {}]}
    for _ in range(3):
        plugin._zonesByName(rep)
    assert plugin.logger.warning.call_count == 2


def test_engineers_zone_missing_from_response_is_logged(plugin, hub):
    dev = FakeDev("Kitchen", 0, props={"zoneName": "Kitchen"})
    hub.append(dev)
    plugin.getNeoData.return_value = {"Hall": {"FROST_TEMP": 12}}
    plugin.updateEng()
    dev.updateStateOnServer.assert_not_called()
    assert any("no entry for zone 'Kitchen'" in str(c) for c in plugin.logger.debug.call_args_list)


def test_type_change_supersedes_old_device_and_feeds_new_one(plugin, hub):
    old = FakeDev("Hall Sensor", 0, "heatmiserNeostat", props={"zoneName": "Hall Sensor", "neoDeviceType": "1"})
    hub.append(old)
    plugin.getNeoData.return_value = live([stat("Hall Sensor", DEVICE_TYPE=14)])
    plugin.createDevices()
    assert old.name == "Hall Sensor SUPERSEDED" and old.replaced is True
    new = conftest.indigo_stub.device.create.call_args.kwargs
    conftest.indigo_stub.device.create.assert_called_once()
    assert new["deviceTypeId"] == "heatmiserNeoSensor" and new["props"]["zoneName"] == "Hall Sensor"
    assert updates(plugin) == [("Hall Sensor", "Hall Sensor")]


def test_unknown_type_during_rediscovery_keeps_stored_type_and_never_supersedes(plugin, hub):
    # Gen 2: DEVICE_TYPE comes from GET_ENGINEERS; a blip there must not turn a sensor into a thermostat.
    plugin.neohubGen2 = True
    sensor = FakeDev("Hall Sensor", 0, "heatmiserNeoSensor", props={"zoneName": "Hall Sensor", "neoDeviceType": "14"})
    hub.append(sensor)
    plugin.getNeoData.side_effect = ["", {"devices": [{"ZONE_NAME": "Hall Sensor"}]}]  # GET_ENGINEERS fails, live data has no type
    plugin.createDevices()
    assert sensor.replaced is False and sensor.name == "Hall Sensor"
    assert sensor.pluginProps["neoDeviceType"] == "14"
    conftest.indigo_stub.device.create.assert_not_called()


def test_gen2_type_comes_from_engineers_map_by_zone_name(plugin, hub):
    plugin.neohubGen2 = True
    plugin.getNeoData.side_effect = [{"Hall Sensor": {"DEVICE_TYPE": 14}}, {"devices": [{"ZONE_NAME": "Hall Sensor"}]}]
    plugin.createDevices()
    kw = conftest.indigo_stub.device.create.call_args.kwargs
    assert kw["deviceTypeId"] == "heatmiserNeoSensor" and kw["props"]["neoDeviceType"] == "14"


def test_create_failure_for_one_zone_does_not_block_others(plugin, hub):
    def flaky(**kw):
        if kw["name"].startswith("Kitchen"):
            raise RuntimeError("boom")
        return fake_create(**kw)
    conftest.indigo_stub.device.create.side_effect = flaky
    plugin.getNeoData.return_value = live([stat("Kitchen"), stat("Hall")])
    plugin.createDevices()
    assert updates(plugin) == [("Hall", "Hall")]
    plugin.logger.exception.assert_called_once()
    # A non-clash failure propagates to the per-zone handler: no retry under another name.
    assert [c.kwargs["name"] for c in conftest.indigo_stub.device.create.call_args_list] == ["Kitchen", "Hall"]


def test_name_clash_creates_with_heatmiser_suffix_in_one_call(plugin, hub):
    hub.taken.add("Kitchen")  # another plugin's device already owns the name
    plugin.getNeoData.return_value = live([stat("Kitchen")])
    plugin.createDevices()
    conftest.indigo_stub.device.create.assert_called_once()
    created = conftest.indigo_stub.device.create.call_args.kwargs
    assert created["name"] == "Kitchen Heatmiser"
    assert created["props"]["zoneName"] == "Kitchen"
    assert updates(plugin) == [("Kitchen Heatmiser", "Kitchen")]
    assert any("Indigo already has a device named 'Kitchen'" in str(c) for c in plugin.logger.warning.call_args_list)


def test_sensor_zone_gets_sensor_device_type(plugin, hub):
    plugin.getNeoData.return_value = live([stat("Hall Sensor", DEVICE_TYPE=14)])
    plugin.createDevices()
    kw = conftest.indigo_stub.device.create.call_args.kwargs
    assert kw["deviceTypeId"] == "heatmiserNeoSensor"
    assert kw["props"] == {"neoDeviceType": "14", "zoneName": "Hall Sensor"}


# -------------------------------------------------------------- commands

def test_commands_use_stored_zone_name_not_indigo_name(plugin, action_for, mock_device):
    mock_device.name = "Towel Rail (renamed in Indigo)"
    mock_device.pluginProps = {"zoneName": "Family Bath Towel Rail"}
    plugin.awayOn(action_for())
    plugin.getNeoData.assert_called_once_with('"AWAY_ON":["Family Bath Towel Rail"]')


def test_thermostat_action_uses_stored_zone_name(plugin, mock_device):
    mock_device.name = "Renamed"
    mock_device.pluginProps = {"zoneName": "Kitchen"}
    action = MagicMock()
    action.thermostatAction = conftest.indigo_stub.kThermostatAction.SetHeatSetpoint
    action.actionValue = 21
    plugin.actionControlThermostat(action, mock_device)
    plugin.getNeoData.assert_called_once_with('"SET_TEMP":[21, "Kitchen"]')


def test_relay_action_uses_stored_zone_name(plugin, mock_device):
    mock_device.name = "Renamed"
    mock_device.pluginProps = {"zoneName": "Lamp Socket"}
    action = MagicMock()
    action.deviceAction = conftest.indigo_stub.kDeviceAction.TurnOn
    plugin.actionControlDevice(action, mock_device)
    plugin.getNeoData.assert_called_once_with('"TIMER_ON":["Lamp Socket"]')


def test_engineers_data_looked_up_by_zone_name(plugin, hub):
    dev = FakeDev("Renamed", 0, props={"zoneName": "Kitchen"})
    dev.updateStateOnServer = MagicMock()
    hub.append(dev)
    plugin.getNeoData.return_value = {"Kitchen": {"FROST_TEMP": 12, "SWITCHING DIFFERENTIAL": 1, "RATE OF CHANGE": 20}}
    plugin.updateEng()
    dev.updateStateOnServer.assert_any_call(key="FrostTemp", value=12)


# ------------------------------------------------- review-fix regressions

def test_type_change_while_creation_held_does_not_supersede(plugin, hub):
    mystery = FakeDev("Mystery", 5)  # legacy, matches no zone: holds creation
    old = FakeDev("Hall Sensor", 0, "heatmiserNeostat", props={"zoneName": "Hall Sensor", "neoDeviceType": "1"})
    hub += [mystery, old]
    plugin.getNeoData.return_value = live([stat("Hall Sensor", DEVICE_TYPE=14)])
    plugin.createDevices()
    assert old.name == "Hall Sensor" and old.replaced is False
    assert old.pluginProps["neoDeviceType"] == "1"  # type change deferred, so the stored type still matches the device
    conftest.indigo_stub.device.create.assert_not_called()
    assert updates(plugin) == [("Hall Sensor", "Hall Sensor")]
    assert any("creation is held" in str(c) and "Hall Sensor" in str(c) for c in plugin.logger.warning.call_args_list)


def test_bound_device_whose_zone_vanished_is_flagged_once_and_left_alone(plugin, hub):
    ensuite = FakeDev("Ensuite", 1, props={"zoneName": "Ensuite", "neoDeviceType": "1"})
    hub.append(ensuite)
    plugin.getNeoData.return_value = live([stat("Hall")])
    plugin.createDevices()
    assert ensuite.errorState == "ZONE NOT ON HUB"
    assert ensuite.name == "Ensuite" and ensuite.replaced is False
    assert updates(plugin) == [("Hall", "Hall")]
    assert [c.kwargs["name"] for c in conftest.indigo_stub.device.create.call_args_list] == ["Hall"]
    warnings_for = lambda: sum("Ensuite" in str(c) for c in plugin.logger.warning.call_args_list)
    assert warnings_for() == 1
    plugin.updateReadings()  # next poll must not repeat the warning
    assert warnings_for() == 1
    assert ensuite.errorState == "ZONE NOT ON HUB"
    assert ("Ensuite", "Ensuite") not in updates(plugin)


def test_superseded_device_sharing_zone_name_is_never_fed(plugin, hub):
    old = FakeDev("Hall SUPERSEDED", 0, props={"zoneName": "Hall", "neoDeviceType": "1"})
    new = FakeDev("Hall", 0, props={"zoneName": "Hall", "neoDeviceType": "1"})
    hub += [old, new]
    plugin.getNeoData.return_value = live([stat("Hall")])
    plugin.createDevices()
    assert [c.args[2] for c in plugin.updateStatState.call_args_list] == [new]
    plugin.updateStatState.reset_mock()
    plugin.updateReadings()
    assert [c.args[2] for c in plugin.updateStatState.call_args_list] == [new]
    assert old.errorState is None
    plugin.logger.warning.assert_not_called()


def test_rediscovery_that_raises_does_not_advance_stamp_and_is_retried(plugin, hub):
    plugin._deviceListStamp = 100
    toilet = FakeDev("Toilet", 3)  # legacy: migration writes its props
    realReplace = toilet.replacePluginPropsOnServer
    calls = []

    def flaky(props):
        calls.append(props)
        if len(calls) == 1:
            raise RuntimeError("server busy")
        realReplace(props)
    toilet.replacePluginPropsOnServer = flaky
    hub.append(toilet)
    plugin.getNeoData.return_value = live([stat("Toilet")], TIMESTAMP_DEVICE_LISTS=101)
    with pytest.raises(RuntimeError):
        plugin.updateReadings()
    assert plugin._deviceListStamp == 100
    plugin.updateReadings()  # same stamp still differs from ours, so it rediscovers
    assert plugin._deviceListStamp == 101
    assert toilet.pluginProps["zoneName"] == "Toilet"
    assert len(calls) == 2


def test_duplicate_loser_is_flagged_on_discovery_and_poll_and_gets_no_engineering_data(plugin, hub):
    a = FakeDev("Hall A", 0, props={"zoneName": "Hall", "neoDeviceType": "1"})
    b = FakeDev("Hall B", 0, props={"zoneName": "Hall", "neoDeviceType": "1"})
    hub += [a, b]
    plugin.getNeoData.return_value = live([stat("Hall")])
    plugin.createDevices()
    assert a.errorState is None and b.errorState == "DUPLICATE ZONE"
    b.errorState = None
    plugin.updateReadings()
    assert a.errorState is None and b.errorState == "DUPLICATE ZONE"  # re-asserted each poll
    plugin.getNeoData.return_value = {"Hall": {"FROST_TEMP": 12, "SWITCHING DIFFERENTIAL": 1, "RATE OF CHANGE": 20}}
    plugin.updateEng()
    a.updateStateOnServer.assert_any_call(key="FrostTemp", value=12)
    b.updateStateOnServer.assert_not_called()


_ZONE_CALLBACKS = [
    "setCool", "setAuto", "setOverride", "timerBoost", "timerBoostOff", "awayOn", "awayOff", "lockKeypad",
    "unlockKeypad", "cancelHold", "setFrostTemp", "identifyDevice", "getHoursRun", "getTempLog",
]


@pytest.mark.parametrize("callback", _ZONE_CALLBACKS)
def test_unbound_device_refuses_plugin_actions(plugin, action_for, mock_device, callback):
    mock_device.pluginProps = {}  # no zoneName: never bound; the Indigo name must not be used as a zone
    getattr(plugin, callback)(action_for(overrideTemp="21", numberOfHours="1"))
    plugin.getNeoData.assert_not_called()
    plugin.logger.error.assert_called_once()
    assert "not bound to a hub zone" in plugin.logger.error.call_args.args[0]
    assert "TestStat" in plugin.logger.error.call_args.args[0]


def test_unbound_device_refuses_thermostat_action(plugin, mock_device):
    mock_device.pluginProps = {}
    action = MagicMock()
    action.thermostatAction = conftest.indigo_stub.kThermostatAction.SetHeatSetpoint
    action.actionValue = 21
    plugin.actionControlThermostat(action, mock_device)
    plugin.getNeoData.assert_not_called()
    plugin.logger.error.assert_called_once()
    assert "not bound to a hub zone" in plugin.logger.error.call_args.args[0]


def test_unbound_device_refuses_relay_action(plugin, mock_device):
    mock_device.pluginProps = {}
    action = MagicMock()
    action.deviceAction = conftest.indigo_stub.kDeviceAction.TurnOn
    plugin.actionControlDevice(action, mock_device)
    plugin.getNeoData.assert_not_called()
    plugin.logger.error.assert_called_once()
    assert "not bound to a hub zone" in plugin.logger.error.call_args.args[0]


def test_engineers_data_skips_unbound_device_even_if_its_name_matches_a_zone(plugin, hub):
    dev = FakeDev("Kitchen", 0)  # legacy: no zoneName
    hub.append(dev)
    plugin.getNeoData.return_value = {"Kitchen": {"FROST_TEMP": 12, "SWITCHING DIFFERENTIAL": 1, "RATE OF CHANGE": 20}}
    plugin.updateEng()
    dev.updateStateOnServer.assert_not_called()


def test_new_zone_with_unknown_type_is_not_created_but_known_device_is_kept(plugin, hub):
    plugin.neohubGen2 = True
    hall = FakeDev("Hall", 0, props={"zoneName": "Hall", "neoDeviceType": "1"})
    hub.append(hall)
    plugin.getNeoData.side_effect = [{}, live([stat("Hall", DEVICE_TYPE=0), stat("Ensuite", DEVICE_TYPE=0)])]  # GET_ENGINEERS empty
    plugin.createDevices()
    conftest.indigo_stub.device.create.assert_not_called()
    assert updates(plugin) == [("Hall", "Hall")]
    assert hall.replaced is False and hall.errorState is None and hall.pluginProps["neoDeviceType"] == "1"
    warned = [str(c) for c in plugin.logger.warning.call_args_list]
    assert any("GET_ENGINEERS failed" in w for w in warned)
    assert any("Ensuite" in w and "no device type yet" in w for w in warned)


def test_hub_host_has_no_positional_fallback_after_discovery(plugin, hub):
    mystery = FakeDev("Mystery", "0")  # legacy device with a stale address 0: holds creation, binds nothing
    hub.append(mystery)
    plugin._discoveryDone = False
    plugin.getNeoData.return_value = live([stat("Hall"), stat("Kitchen")])
    assert plugin._hubHostDevice() is mystery  # before discovery the address-0 fallback still works
    plugin.createDevices()
    assert plugin._discoveryDone is True
    conftest.indigo_stub.device.create.assert_not_called()
    assert plugin._hubHostDevice() is None
    plugin.logger.exception.assert_not_called()


def test_sync_failure_flags_known_device(plugin, hub):
    hall = FakeDev("Hall", 0, props={"zoneName": "Hall", "neoDeviceType": "1"})
    kitchen = FakeDev("Kitchen", 1, props={"zoneName": "Kitchen", "neoDeviceType": "1"})
    hub += [hall, kitchen]

    def feed(rep, index, dev):
        if dev is hall:
            raise RuntimeError("bad data")
    plugin.updateStatState.side_effect = feed
    plugin.getNeoData.return_value = live([stat("Hall"), stat("Kitchen")])
    plugin.createDevices()
    assert hall.errorState == "SYNC FAILED"
    assert kitchen.errorState is None
    plugin.logger.exception.assert_called_once()
    assert plugin._discoveryDone is True


def test_sync_failure_flagging_cannot_itself_raise(plugin, hub):
    hall = FakeDev("Hall", 0, props={"zoneName": "Hall", "neoDeviceType": "1"})
    hall.setErrorStateOnServer = MagicMock(side_effect=RuntimeError("server gone"))
    hub.append(hall)
    plugin.updateStatState.side_effect = RuntimeError("bad data")
    plugin.getNeoData.return_value = live([stat("Hall")])
    plugin.createDevices()  # must not raise
    assert plugin._discoveryDone is True
    plugin.logger.debug.assert_called()


# ------------------------------------------------- sensor offline is an error state

def test_offline_sensor_gets_offline_error_state_and_online_reading_clears_it(plugin):
    dev = FakeDev("Loft", 3, typeId="heatmiserNeoSensor", props={"zoneName": "Loft", "neoDeviceType": "14"})
    offline = live([stat("Loft", DEVICE_TYPE=14, OFFLINE=True)])
    plugin.updateStatState(offline, 0, dev)
    assert dev.errorState == "OFFLINE"
    online = live([stat("Loft", DEVICE_TYPE=14, OFFLINE=False)])
    plugin.updateStatState(online, 0, dev)
    written = dev.updateStatesOnServer.call_args.args[0]
    temp = next(s for s in written if s["key"] == "temperatureInput1")
    assert temp["value"] == temp_of("Loft") and temp.get("clearErrorState") is True
