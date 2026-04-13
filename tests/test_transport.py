"""TCP transport tests for `_get_neo_data_tcp`.

Mocks `socket.socket` and feeds chunked `.recv()` responses to verify:
- single-packet commands return parsed JSON
- multi-packet responses for GET_LIVE_DATA / GET_ENGINEERS / GET_HOURSRUN /
  GET_TEMPLOG assemble correctly until the terminator appears
- `{"error": ...}` envelope returns "" and logs
- non-printable bytes are filtered before JSON parse
- the socket is closed even when send raises
"""
import socket
from unittest.mock import MagicMock, patch


def _make_fake_socket(chunks):
    """Build a fake socket whose recv() returns the given byte chunks then b''."""
    sock = MagicMock(spec=socket.socket)
    sock.recv.side_effect = list(chunks) + [b""]
    return sock


def test_single_packet_command_parses_ok(plugin):
    fake = _make_fake_socket([b'{"result":"ok"}'])
    with patch("socket.socket", return_value=fake):
        result = plugin._get_neo_data_tcp('"AWAY_ON":["X"]')
    assert result == {"result": "ok"}
    fake.close.assert_called_once()


def test_get_live_data_assembles_multi_packet(plugin):
    # Split a valid GET_LIVE_DATA response across three recv() calls.
    # Terminator check looks at dataj[-5:-1], so we append a trailing null
    # byte (matching what the real hub protocol sends).
    full = b'{"devices":[{"name":"A"},{"name":"B"}]}\x00'
    chunks = [full[:15], full[15:30], full[30:]]
    fake = _make_fake_socket(chunks)
    with patch("socket.socket", return_value=fake):
        result = plugin._get_neo_data_tcp('"GET_LIVE_DATA":0')
    assert result == {"devices": [{"name": "A"}, {"name": "B"}]}
    assert fake.recv.call_count == 3


def test_get_hoursrun_assembles_multi_packet(plugin):
    """Regression test for the PR #22 TCP truncation fix."""
    full = b'{"day:1":{"Kitchen":0},"today":{"Kitchen":12}}\x00'
    chunks = [full[:20], full[20:]]
    fake = _make_fake_socket(chunks)
    with patch("socket.socket", return_value=fake):
        result = plugin._get_neo_data_tcp('"GET_HOURSRUN":"Kitchen"')
    assert result == {"day:1": {"Kitchen": 0}, "today": {"Kitchen": 12}}
    assert fake.recv.call_count == 2


def test_get_templog_assembles_multi_packet(plugin):
    """Regression test for the PR #22 TCP truncation fix."""
    full = b'{"day:1":{"Kitchen":[20,21]},"today":{"Kitchen":[22]}}\x00'
    chunks = [full[:25], full[25:]]
    fake = _make_fake_socket(chunks)
    with patch("socket.socket", return_value=fake):
        result = plugin._get_neo_data_tcp('"GET_TEMPLOG":["Kitchen"]')
    assert "day:1" in result
    assert fake.recv.call_count == 2


def test_get_engineers_assembles_multi_packet(plugin):
    full = b'{"StatA":{"RATE OF CHANGE":5}}\x00'
    chunks = [full[:12], full[12:]]
    fake = _make_fake_socket(chunks)
    with patch("socket.socket", return_value=fake):
        result = plugin._get_neo_data_tcp('"GET_ENGINEERS":0')
    assert result == {"StatA": {"RATE OF CHANGE": 5}}


def test_error_envelope_returns_empty_string(plugin):
    fake = _make_fake_socket([b'{"error":"bad command"}'])
    with patch("socket.socket", return_value=fake):
        result = plugin._get_neo_data_tcp('"BOGUS":0')
    assert result == ""
    plugin.logger.error.assert_called()


def test_non_printable_bytes_are_filtered(plugin):
    fake = _make_fake_socket([b'\x00\x01{"result":"ok"}\xff'])
    with patch("socket.socket", return_value=fake):
        result = plugin._get_neo_data_tcp('"AWAY_ON":["X"]')
    assert result == {"result": "ok"}


def test_socket_closed_on_send_exception(plugin):
    fake = _make_fake_socket([b''])
    fake.send.side_effect = socket.error("boom")
    with patch("socket.socket", return_value=fake):
        result = plugin._get_neo_data_tcp('"AWAY_ON":["X"]')
    assert result == ""
    fake.close.assert_called_once()


def test_socket_closed_on_connect_exception(plugin):
    fake = MagicMock(spec=socket.socket)
    fake.connect.side_effect = socket.timeout("timeout")
    with patch("socket.socket", return_value=fake):
        result = plugin._get_neo_data_tcp('"AWAY_ON":["X"]')
    assert result == ""
    fake.close.assert_called_once()


def test_comms_disabled_short_circuits(plugin):
    plugin.commsEnabled = False
    from plugin import Plugin
    # Fixture mocks getNeoData; call the real method via the class
    assert Plugin.getNeoData(plugin, '"AWAY_ON":["X"]') == ""


def test_getNeoData_routes_to_tcp_when_mode_tcp(plugin):
    plugin.connectionMode = "tcp"
    plugin._get_neo_data_tcp = MagicMock(return_value={"ok": True})
    plugin._get_neo_data_wss = MagicMock()
    # Re-bind getNeoData from the class since the fixture mocks it
    from plugin import Plugin
    result = Plugin.getNeoData(plugin, '"AWAY_ON":["X"]')
    assert result == {"ok": True}
    plugin._get_neo_data_tcp.assert_called_once()
    plugin._get_neo_data_wss.assert_not_called()
