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

    def replacePluginPropsOnServer(self, props):
        self.pluginProps = dict(props)

    def replaceOnServer(self):
        self.replaced = True


def stat(name, **extra):
    d = {"ZONE_NAME": name, "DEVICE_TYPE": 1, "ACTUAL_TEMP": 20.0, "SET_TEMP": 21}
    d.update(extra)
    return d


def live(devices, **hub):
    rep = {"devices": devices}
    rep.update(hub)
    return rep


@pytest.fixture
def hub(plugin):
    """Wire indigo.devices.iter to a mutable list and capture updateStatState calls."""
    devs = []
    conftest.indigo_stub.devices.iter = MagicMock(side_effect=lambda *_: list(devs))
    conftest.indigo_stub.device.create = MagicMock(
        side_effect=lambda **kw: FakeDev(kw["name"], kw["address"], kw["deviceTypeId"], kw["props"])
    )
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
    assert updates(plugin) == {"Hall": 0}
    assert any("Ensuite" in str(c) for c in plugin.logger.warning.call_args_list)


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
    assert "Downstairs Loo" not in updates(plugin)
    warned = " ".join(str(c) for c in plugin.logger.warning.call_args_list)
    assert "Downstairs Loo" in warned and "Toilet" in warned


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
