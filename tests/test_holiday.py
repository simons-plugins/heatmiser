"""setHoliday() date/time parsing edge cases.

Covers the failure branches (invalid/missing date, invalid time, past
date) and the success path. The success-path assertion ignores the
runtime-dependent `now` portion of the HOLIDAY command and validates
the deterministic end-time portion only.
"""
from unittest.mock import MagicMock


def _action(**props):
    a = MagicMock()
    a.props = props
    return a


def test_missing_date_logs_error(plugin):
    plugin.setHoliday(_action())
    plugin.logger.error.assert_called_once()
    plugin.getNeoData.assert_not_called()


def test_invalid_date_format_logs_error(plugin):
    plugin.setHoliday(_action(holidayEndDate="not-a-date"))
    plugin.logger.error.assert_called_once()
    plugin.getNeoData.assert_not_called()


def test_invalid_time_format_logs_error(plugin):
    plugin.setHoliday(_action(holidayEndDate="31/12/2099", holidayEndTime="bogus"))
    plugin.logger.error.assert_called_once()
    plugin.getNeoData.assert_not_called()


def test_past_date_logs_error(plugin):
    plugin.setHoliday(_action(holidayEndDate="01/01/2020", holidayEndTime="12:00"))
    plugin.logger.error.assert_called_once()
    assert "not in the future" in plugin.logger.error.call_args.args[0]
    plugin.getNeoData.assert_not_called()


def test_valid_future_date_builds_holiday_command(plugin):
    plugin.setHoliday(_action(holidayEndDate="31/12/2099", holidayEndTime="14:30"))
    plugin.getNeoData.assert_called_once()
    cmd = plugin.getNeoData.call_args.args[0]
    # Format is: "HOLIDAY":["<start>","<end>"] where end = HHMM00DDMMYYYY
    assert cmd.startswith('"HOLIDAY":["')
    assert '"143000311220 99"'.replace(" ", "") in cmd or "143000311220 99".replace(" ", "") in cmd
    # Exact end-string check
    assert ',"143000' in cmd  # HH=14 MM=30 SS=00
    assert '31122099"]' in cmd  # DD=31 MM=12 YYYY=2099


def test_dates_with_whitespace_are_trimmed(plugin):
    plugin.setHoliday(_action(holidayEndDate="  31/12/2099  ", holidayEndTime=" 09:15 "))
    plugin.getNeoData.assert_called_once()
    cmd = plugin.getNeoData.call_args.args[0]
    assert ',"091500' in cmd
    assert '31122099"]' in cmd
