"""Shared fixtures and the `indigo` module stub.

The heatmiser plugin `plugin.py` does `import indigo` and inherits from
`indigo.PluginBase` at class-definition time, so we must inject a stub
into `sys.modules` before any test imports the plugin module.
"""
import builtins
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest


# 1. Stub `indigo` module before plugin.py can import it
class _HvacModeStub:
    ProgramHeat = "ProgramHeat"
    Heat = "Heat"
    Cool = "Cool"
    Off = "Off"


indigo_stub = ModuleType("indigo")
indigo_stub.PluginBase = object  # plugin.py does `class Plugin(indigo.PluginBase)`
indigo_stub.kHvacMode = _HvacModeStub
indigo_stub.devices = MagicMock()
indigo_stub.variables = MagicMock()
indigo_stub.variable = MagicMock()
indigo_stub.server = MagicMock()
sys.modules["indigo"] = indigo_stub
# Indigo's runtime injects `indigo` as an implicit global; plugin.py never
# does `import indigo`. Put it in builtins so the plugin module sees it.
builtins.indigo = indigo_stub


# 2. Add Server Plugin directory to sys.path so `import plugin` works
SERVER_PLUGIN_DIR = (
    Path(__file__).parent.parent
    / "HeatmiserNeo.IndigoPlugin"
    / "Contents"
    / "Server Plugin"
)
sys.path.insert(0, str(SERVER_PLUGIN_DIR))


@pytest.fixture
def plugin():
    """Construct a Plugin instance bypassing __init__.

    Injects the minimum attributes the methods under test reference.
    Tests patch `plugin.getNeoData` to a MagicMock to observe commands
    or stub responses.
    """
    from plugin import Plugin

    p = Plugin.__new__(Plugin)
    p.logger = MagicMock()
    p.neohubIP = "192.168.0.1"
    p.neohubToken = "test-token"
    p.connectionMode = "tcp"
    p.logComms = False
    p.commsEnabled = True
    p.neohubGen2 = False
    p.connectErrorCount = 0
    p.sendErrorCount = 0
    p.neoDevice = None
    p.getNeoData = MagicMock(return_value={"result": "ok"})
    return p


@pytest.fixture
def mock_device():
    """A mock indigo device with a configurable name."""
    dev = MagicMock()
    dev.name = "TestStat"
    dev.deviceTypeId = "heatmiserNeostat"
    dev.id = 12345
    return dev


@pytest.fixture
def action_for(mock_device):
    """Factory that builds a plugin action bound to the mock device."""
    def _make(**props):
        action = MagicMock()
        action.deviceId = mock_device.id
        action.props = props
        return action
    # Wire indigo.devices[id] to return the mock device
    indigo_stub.devices.__getitem__ = MagicMock(return_value=mock_device)
    return _make
