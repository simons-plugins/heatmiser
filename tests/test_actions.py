"""Action callback command-builder assertions.

Each test patches `plugin.getNeoData` and asserts the exact `cmdPhrase`
argument the callback builds. This catches regressions in API command
syntax — e.g. scalar-vs-array device args, quoting, field order.
"""


def test_awayOn_builds_correct_command(plugin, action_for):
    action = action_for()
    plugin.awayOn(action)
    plugin.getNeoData.assert_called_once_with('"AWAY_ON":["TestStat"]')


def test_awayOff_builds_correct_command(plugin, action_for):
    action = action_for()
    plugin.awayOff(action)
    plugin.getNeoData.assert_called_once_with('"AWAY_OFF":["TestStat"]')


def test_cancelHold_builds_correct_command(plugin, action_for):
    action = action_for()
    plugin.cancelHold(action)
    plugin.getNeoData.assert_called_once_with(
        '"HOLD":[{"temp":20, "id":"Off", "hours":0, "minutes":0}, "TestStat"]'
    )


def test_unlockKeypad_builds_correct_command(plugin, action_for):
    action = action_for()
    plugin.unlockKeypad(action)
    plugin.getNeoData.assert_called_once_with('"UNLOCK":["TestStat"]')


def test_lockKeypad_splits_pin_into_digits(plugin, action_for):
    action = action_for(lockPin="1234")
    plugin.lockKeypad(action)
    plugin.getNeoData.assert_called_once_with('"LOCK":[[1,2,3,4], ["TestStat"]]')


def test_lockKeypad_defaults_to_0000(plugin, action_for):
    action = action_for()
    plugin.lockKeypad(action)
    plugin.getNeoData.assert_called_once_with('"LOCK":[[0,0,0,0], ["TestStat"]]')


def test_setFrostTemp_uses_configured_temp(plugin, action_for):
    action = action_for(frostTemp="10")
    plugin.setFrostTemp(action)
    plugin.getNeoData.assert_called_once_with('"SET_FROST":[10, "TestStat"]')


def test_identifyDevice_builds_correct_command(plugin, action_for):
    action = action_for()
    plugin.identifyDevice(action)
    plugin.getNeoData.assert_called_once_with('"IDENTIFY":[1, 3, ["TestStat"]]')


def test_timerBoost_uses_configured_minutes(plugin, action_for):
    action = action_for(boostMinutes="60")
    plugin.timerBoost(action)
    plugin.getNeoData.assert_called_once_with('"TIMER_HOLD_ON":[60, "TestStat"]')


def test_timerBoost_defaults_to_30min(plugin, action_for):
    action = action_for()
    plugin.timerBoost(action)
    plugin.getNeoData.assert_called_once_with('"TIMER_HOLD_ON":[30, "TestStat"]')


def test_timerBoostOff_sends_zero_minutes(plugin, action_for):
    action = action_for()
    plugin.timerBoostOff(action)
    plugin.getNeoData.assert_called_once_with('"TIMER_HOLD_ON":[0, "TestStat"]')


def test_setCool_builds_frost_on(plugin, action_for):
    action = action_for()
    plugin.setCool(action)
    plugin.getNeoData.assert_called_once_with('"FROST_ON":["TestStat"]')


def test_setCool_skips_unsupported_device_type(plugin, action_for, mock_device):
    mock_device.deviceTypeId = "heatmiserNeoPlug"
    action = action_for()
    plugin.setCool(action)
    plugin.getNeoData.assert_not_called()
    plugin.logger.warning.assert_called_once()


def test_setAuto_sends_frost_off_then_hold_off(plugin, action_for):
    action = action_for()
    plugin.setAuto(action)
    assert plugin.getNeoData.call_count == 2
    first_call = plugin.getNeoData.call_args_list[0].args[0]
    second_call = plugin.getNeoData.call_args_list[1].args[0]
    assert first_call == '"FROST_OFF":["TestStat"]'
    assert second_call == (
        '"HOLD":[{"temp":20, "id":"Off", "hours":0, "minutes":0}, "TestStat"]'
    )


def test_setOverride_full_hour(plugin, action_for):
    action = action_for(overrideTemp="21", numberOfHours="02")
    plugin.setOverride(action)
    plugin.getNeoData.assert_called_once_with(
        '"HOLD":[{"temp":21, "id":"Off", "hours":02, "minutes":0}, "TestStat"]'
    )


def test_setOverride_30min_splits_to_minutes(plugin, action_for):
    action = action_for(overrideTemp="20", numberOfHours="0.5")
    plugin.setOverride(action)
    plugin.getNeoData.assert_called_once_with(
        '"HOLD":[{"temp":20, "id":"Off", "hours":0, "minutes":30}, "TestStat"]'
    )


def test_cancelHoliday_builds_correct_command(plugin, action_for):
    action = action_for()
    plugin.cancelHoliday(action)
    plugin.getNeoData.assert_called_once_with('"CANCEL_HOLIDAY":0')


def test_getHoursRun_uses_scalar_device_arg(plugin, action_for):
    """API docs example uses scalar form: {"GET_HOURSRUN":"Kitchen"}"""
    plugin.getNeoData.return_value = {"day:1": {"TestStat": 5}}
    action = action_for()
    plugin.getHoursRun(action)
    plugin.getNeoData.assert_called_once_with('"GET_HOURSRUN":"TestStat"')


def test_getTempLog_uses_array_device_arg(plugin, action_for):
    """API docs example uses array form: {"GET_TEMPLOG":["Kitchen"]}"""
    plugin.getNeoData.return_value = {"day:1": {"TestStat": [20, 21]}}
    action = action_for()
    plugin.getTempLog(action)
    plugin.getNeoData.assert_called_once_with('"GET_TEMPLOG":["TestStat"]')


def test_getHoursRun_logs_error_on_empty_response(plugin, action_for):
    plugin.getNeoData.return_value = ""
    action = action_for()
    plugin.getHoursRun(action)
    plugin.logger.error.assert_called_once()
    plugin.logger.info.assert_not_called()


def test_getTempLog_logs_error_on_empty_response(plugin, action_for):
    plugin.getNeoData.return_value = ""
    action = action_for()
    plugin.getTempLog(action)
    plugin.logger.error.assert_called_once()
    plugin.logger.info.assert_not_called()
