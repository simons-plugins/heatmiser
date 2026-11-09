"""Command failures are logged, and a half-sent multi-command sequence never reports success."""
import pytest

import conftest

K = conftest.indigo_stub.kThermostatAction


def thermostat_action(kind, **kw):
    from unittest.mock import MagicMock
    action = MagicMock()
    action.thermostatAction = getattr(K, kind)
    for k, v in kw.items():
        setattr(action, k, v)
    return action


def sent(plugin):
    return [c.args[0] for c in plugin.getNeoData.call_args_list]


@pytest.mark.parametrize("kind", ["SetHeatSetpoint", "DecreaseHeatSetpoint", "IncreaseHeatSetpoint"])
def test_setpoint_failure_logs_error(plugin, mock_device, kind):
    mock_device.heatSetpoint = 20
    plugin.getNeoData.return_value = ""
    plugin.actionControlThermostat(thermostat_action(kind, actionValue=1), mock_device)
    mock_device.updateStateOnServer.assert_not_called()
    plugin.logger.error.assert_called_once()
    assert "setpoint command failed" in plugin.logger.error.call_args.args[0]


@pytest.mark.parametrize("mode,failing", [
    (conftest.indigo_stub.kHvacMode.HeatCool, "FROST_OFF"),
    (conftest.indigo_stub.kHvacMode.Heat, "FROST_OFF"),
    (conftest.indigo_stub.kHvacMode.Cool, "HOLD"),
])
def test_hvac_mode_first_command_failure_logs_and_does_not_update_mode(plugin, mock_device, mode, failing):
    plugin.getNeoData.return_value = ""
    plugin.actionControlThermostat(thermostat_action("SetHvacMode", actionMode=mode), mock_device)
    assert len(sent(plugin)) == 1                        # the second command is never sent
    mock_device.updateStateOnServer.assert_not_called()
    assert any("%s command failed" % failing in c.args[0] for c in plugin.logger.error.call_args_list)


def test_hvac_mode_success_updates_mode(plugin, mock_device):
    plugin.actionControlThermostat(thermostat_action("SetHvacMode", actionMode=conftest.indigo_stub.kHvacMode.Heat), mock_device)
    assert len(sent(plugin)) == 2
    mock_device.updateStateOnServer.assert_called_once_with("hvacOperationMode", conftest.indigo_stub.kHvacMode.Heat)
    plugin.logger.error.assert_not_called()


def test_hvac_mode_second_command_failure_does_not_update_mode(plugin, mock_device):
    plugin.getNeoData.side_effect = [{"result": "ok"}, ""]
    plugin.actionControlThermostat(thermostat_action("SetHvacMode", actionMode=conftest.indigo_stub.kHvacMode.Heat), mock_device)
    mock_device.updateStateOnServer.assert_not_called()
    plugin.logger.error.assert_called_once()


def test_unsupported_hvac_mode_logs_error_without_raising(plugin, mock_device):
    plugin.actionControlThermostat(thermostat_action("SetHvacMode", actionMode="FanOnly"), mock_device)
    plugin.getNeoData.assert_not_called()
    mock_device.updateStateOnServer.assert_not_called()
    assert "not supported" in plugin.logger.error.call_args.args[0]


def test_setAuto_frost_off_failure_logs_and_does_not_send_hold(plugin, action_for):
    plugin.getNeoData.return_value = ""
    plugin.setAuto(action_for())
    assert sent(plugin) == ['"FROST_OFF":["TestStat"]']
    assert "Auto command failed (FROST_OFF)" in plugin.logger.error.call_args.args[0]


def test_setAuto_success_sends_both_commands(plugin, action_for):
    plugin.setAuto(action_for())
    assert len(sent(plugin)) == 2
    plugin.logger.error.assert_not_called()
