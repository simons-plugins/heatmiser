"""Device discovery and polling match on the hub's ZONE_NAME, not list position.

Regression tests for issue #33: removing a stat from the NeoHub shifts
every later device up one slot, and address-based matching silently fed
each Indigo device its neighbour's readings.
"""
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

    def replacePluginPropsOnServer(self, props):
        self.pluginProps = dict(props)

    def replaceOnServer(self):
        self.replaced = True

    def setErrorStateOnServer(self, text):
        self.errorState = text


def stat(name, **extra):
    d = {"ZONE_NAME": name, "DEVICE_TYPE": 1, "ACTUAL_TEMP": 20.0, "SET_TEMP": 21}
    d.update(extra)
    return d


def live(devices, **hub):
    rep = {"devices": devices}
    rep.update(hub)
    return rep


def fake_create(**kw):
    return FakeDev(kw["name"], kw["address"], kw["deviceTypeId"], kw["props"])


@pytest.fixture
def hub(plugin, monkeypatch):
    """Wire indigo.devices.iter to a mutable list and capture updateStatState calls."""
    devs = []
    monkeypatch.setattr(conftest.indigo_stub.devices, "iter", MagicMock(side_effect=lambda *_: list(devs)))
    monkeypatch.setattr(conftest.indigo_stub.device, "create", MagicMock(side_effect=fake_create))
    plugin.updateStatState = MagicMock()
    plugin.updateStatState.side_effect = None
    return devs


def updates(plugin):
    """{device name: hub index it was fed} from updateStatState calls."""
    return {c.args[2].name: c.args[1] for c in plugin.updateStatState.call_args_list}


# ---------------------------------------------------------------- polling

def test_removing_middle_device_keeps_every_reading_on_its_own_zone(plugin, hub):
    # Devices were created when Toilet was at 11 and Kitchen at 12; Ensuite (10) has since been removed.
    hub += [
        FakeDev("Hall", 9, props={"zoneName": "Hall"}),
        FakeDev("Toilet", 11, props={"zoneName": "Toilet"}),
        FakeDev("Kitchen", 12, props={"zoneName": "Kitchen"}),
    ]
    plugin.getNeoData.return_value = live([stat("Hall"), stat("Toilet"), stat("Kitchen")])
    plugin.updateReadings()
    assert updates(plugin) == {"Hall": 0, "Toilet": 1, "Kitchen": 2}


def test_zone_missing_from_hub_is_warned_not_fed_a_neighbour(plugin, hub):
    hub += [
        FakeDev("Hall", 0, props={"zoneName": "Hall"}),
        FakeDev("Ensuite", 1, props={"zoneName": "Ensuite"}),
    ]
    plugin.getNeoData.return_value = live([stat("Hall"), stat("Kitchen")])
    plugin.updateReadings()
    plugin.updateReadings()
    assert updates(plugin) == {"Hall": 0}
    assert hub[1].errorState == "ZONE NOT ON HUB"  # the device itself carries the signal, not just the log
    assert sum("Ensuite" in str(c) for c in plugin.logger.warning.call_args_list) == 1  # once, not every poll


def test_zone_that_leaves_returns_and_leaves_again_is_warned_twice(plugin, hub):
    hub += [FakeDev("Hall", 0, props={"zoneName": "Hall"})]
    for devices in ([], [stat("Hall")], []):
        plugin.getNeoData.return_value = live(devices)
        plugin.updateReadings()
    assert sum("Hall" in str(c) for c in plugin.logger.warning.call_args_list) == 2


def test_duplicate_zone_claim_only_first_device_polled(plugin, hub):
    a = FakeDev("Hall A", 0, props={"zoneName": "Hall"})
    b = FakeDev("Hall B", 0, props={"zoneName": "Hall"})
    hub += [a, b]
    plugin.getNeoData.return_value = live([stat("Hall")])
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
    assert updates(plugin) == {"Toilet": 0}


def test_gen1_info_response_matches_on_device_key(plugin, hub):
    hub += [FakeDev("Hall", 5, props={"zoneName": "Hall"})]
    plugin.getNeoData.return_value = {"devices": [{"device": "Kitchen", "DEVICE_TYPE": 1}, {"device": "Hall", "DEVICE_TYPE": 1}]}
    plugin.updateReadings()
    assert updates(plugin) == {"Hall": 1}
    plugin.createDevices()
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
    plugin.getNeoData.return_value = live([stat("Hall"), stat("Kitchen"), stat("Toilet")])
    plugin.updateReadings()
    assert updates(plugin) == {}


def test_device_list_change_triggers_rediscovery(plugin, hub):
    plugin.createDevices = MagicMock()
    plugin._deviceListStamp = 100
    plugin.getNeoData.return_value = live([stat("Hall")], TIMESTAMP_DEVICE_LISTS=101)
    plugin.updateReadings()
    plugin.createDevices.assert_called_once()


def test_unchanged_device_list_does_not_rediscover(plugin, hub):
    plugin.createDevices = MagicMock()
    plugin._deviceListStamp = 100
    plugin.getNeoData.return_value = live([stat("Hall")], TIMESTAMP_DEVICE_LISTS=100)
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
    assert updates(plugin) == {"Toilet": 0, "Ensuite": 1}


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
    assert updates(plugin)["Toilet"] == 1
    assert updates(plugin)["Family Bath Towel Rail Heatmiser"] == 0
    # Kitchen had no device: created, not forced onto the renamed one.
    assert conftest.indigo_stub.device.create.call_args.kwargs["name"] == "Kitchen"


def test_migration_leaves_renamed_device_alone_and_warns(plugin, hub):
    loo = FakeDev("Downstairs Loo", 1)  # renamed in Indigo before upgrading; hub zone is "Toilet"
    hub.append(loo)
    plugin.getNeoData.return_value = live([stat("Hall"), stat("Toilet")])
    plugin.createDevices()
    assert "zoneName" not in loo.pluginProps
    assert loo.replaced is False
    assert loo.errorState == "NO HUB ZONE"
    assert "Downstairs Loo" not in updates(plugin)
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
    assert conftest.indigo_stub.device.create.call_args.kwargs["name"] == "Hall"


def test_hub_host_is_device_bound_to_zone_at_position_zero(plugin, hub):
    stale = FakeDev("Old Hall", 0, props={"zoneName": "Gone Zone"})   # kept stale address 0
    hall = FakeDev("Hall", 7, props={"zoneName": "Hall", "neoDeviceType": "1"})
    hub += [stale, hall]
    plugin.getNeoData.return_value = live([stat("Hall"), stat("Kitchen")])
    plugin.createDevices()
    assert plugin._hubHostDevice() is hall


def test_failed_hub_response_changes_nothing(plugin, hub):
    dev = FakeDev("Hall", 0, props={"zoneName": "Hall"})
    hub.append(dev)
    plugin._deviceListStamp = 42
    plugin.getNeoData.return_value = ""
    plugin.createDevices()
    conftest.indigo_stub.device.create.assert_not_called()
    assert dev.replaced is False and dev.errorState is None
    assert plugin._deviceListStamp == 42
    plugin.logger.error.assert_called_once()


def test_type_change_supersedes_old_device_and_feeds_new_one(plugin, hub):
    old = FakeDev("Hall Sensor", 0, "heatmiserNeostat", props={"zoneName": "Hall Sensor", "neoDeviceType": "1"})
    hub.append(old)
    plugin.getNeoData.return_value = live([stat("Hall Sensor", DEVICE_TYPE=14)])
    plugin.createDevices()
    assert old.name == "Hall Sensor SUPERSEDED" and old.replaced is True
    new = conftest.indigo_stub.device.create.call_args.kwargs
    assert new["deviceTypeId"] == "heatmiserNeoSensor" and new["props"]["zoneName"] == "Hall Sensor"
    assert [c.args[2].name for c in plugin.updateStatState.call_args_list] == ["Hall Sensor"]


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
    assert "Hall" in updates(plugin)
    plugin.logger.exception.assert_called_once()


def test_name_clash_on_create_falls_back_to_heatmiser_suffix(plugin, hub):
    def clash(**kw):
        if kw["name"] == "Kitchen":
            raise ValueError("NameNotUniqueError")
        return fake_create(**kw)
    conftest.indigo_stub.device.create.side_effect = clash
    plugin.getNeoData.return_value = live([stat("Kitchen")])
    plugin.createDevices()
    assert updates(plugin) == {"Kitchen Heatmiser": 0}
    created = conftest.indigo_stub.device.create.call_args.kwargs
    assert created["props"]["zoneName"] == "Kitchen"


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
