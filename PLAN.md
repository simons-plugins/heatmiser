# Heatmiser Plugin Improvement Plan

## Overview

Systematic improvement of the Heatmiser Neo Indigo plugin, addressing bugs, API compliance, and code quality issues identified in review. Issues tracked at https://github.com/simons-plugins/heatmiser/issues

## Execution Strategy

Each phase is a single commit. Phases are ordered to avoid conflicts and build on each other. Start a fresh context session for execution using `/gsd:resume-work` or by referencing this plan.

---

## Phase 1: Critical Bug Fixes

**Goal**: Fix bugs that cause crashes, resource leaks, or incorrect behavior. No feature changes.

| Task | Issue | File | Description |
|------|-------|------|-------------|
| 1.1 | #1 | plugin.py | Fix socket leak in `getNeoData()` - add `try/finally` with `sock.close()`, make socket a local variable |
| 1.2 | #2 | plugin.py:427 | Fix `pfiString == pfi` → `pfiString = pfi` |
| 1.3 | #3 | plugin.py | Guard `self.neoDevice` access in `updateDCB()` with None check |
| 1.4 | #4 | plugin.py:149,466 | Change bare `except:` to `except Exception:` |
| 1.5 | #9 | plugin.py | Wrap `updateReadings()` and other calls in `runConcurrentThread` with try/except |
| 1.6 | #13 | plugin.py | Fix `updateEng()` to iterate plugin devices directly instead of range-based loop |

**Commit message**: `Fix critical bugs: socket leak, bare excepts, None refs, thread safety`

---

## Phase 2: Code Modernization

**Goal**: Bring code up to Indigo SDK best practices without changing behavior.

| Task | Issue | File | Description |
|------|-------|------|-------------|
| 2.1 | #10 | plugin.py | Modernize `__init__`: use `super().__init__()` with `**kwargs` |
| 2.2 | #10 | plugin.py | Remove `__del__` method |
| 2.3 | #10 | plugin.py | Remove unused imports (`http.client`, `urllib`, `errno`) |
| 2.4 | #10 | plugin.py | Remove dead `fixStatName()` method |
| 2.5 | #7 | plugin.py | Replace all `indigo.server.log()` with `self.logger.info/error/debug` |
| 2.6 | #8 | plugin.py | Convert `updateStatState()` to use batch `updateStatesOnServer()` |
| 2.7 | #12 | plugin.py | Simplify action handlers to use `indigo.devices[id]` instead of iteration |
| 2.8 | #12 | plugin.py | Fix "every minute" log message to say "every 30 seconds" |

**Commit message**: `Modernize plugin: self.logger, batch updates, super(), cleanup dead code`

---

## Phase 3: API Migration

**Goal**: Replace deprecated API commands with their modern equivalents. Still using legacy TCP port.

| Task | Issue | File | Description |
|------|-------|------|-------------|
| 3.1 | #6 | plugin.py | Replace `{"INFO":0}` with `{"GET_LIVE_DATA":0}` in `createDevices()` and `updateReadings()` |
| 3.2 | #6 | plugin.py | Update multi-packet detection for new command name |
| 3.3 | #6 | plugin.py | Verify/update field name mappings in `updateStatState()` against GET_LIVE_DATA response |
| 3.4 | #6 | plugin.py | Replace `{"READ_DCB":100}` with `{"GET_SYSTEM":0}` in `updateDCB()` and update field mappings |
| 3.5 | #6 | plugin.py | Replace `{"ENGINEERS_DATA":0}` with `{"GET_ENGINEERS":0}` in `updateEng()` and update field mappings |
| 3.6 | - | plugin.py | Update multi-packet response detection for `GET_ENGINEERS` command name |

**Commit message**: `Migrate to non-deprecated API commands (GET_LIVE_DATA, GET_SYSTEM, GET_ENGINEERS)`

**Note**: This phase requires testing against a live NeoHub to verify response format differences. The field names may differ between deprecated and new commands.

---

## Phase 4: WebSocket Migration

**Goal**: Replace legacy TCP port 4242 with secure WebSocket port 4243 and token auth.

| Task | Issue | File | Description |
|------|-------|------|-------------|
| 4.1 | #5 | PluginConfig.xml | Add `apiToken` field and `connectionMode` dropdown (WSS/Legacy) |
| 4.2 | #5 | plugin.py | Add `websocket-client` or use `ssl` + built-in websocket support |
| 4.3 | #5 | plugin.py | Create new `getNeoDataWSS()` method with token-wrapped command format |
| 4.4 | #5 | plugin.py | Implement persistent WSS connection (connect once, reuse) |
| 4.5 | #5 | plugin.py | Parse WSS response format (extract `response` field from wrapper) |
| 4.6 | #5 | plugin.py | Add connection mode switching in `getNeoData()` based on preference |
| 4.7 | #5 | plugin.py | Handle WSS reconnection on disconnect |
| 4.8 | #5 | plugin.py | Update `closedPrefsConfigUi` for new config fields |

**Commit message**: `Add WebSocket port 4243 support with token authentication`

**Note**: Keep legacy TCP as fallback. This is the largest change and needs thorough testing. Consider bundling `websocket-client` in `Contents/Packages/`.

---

## Phase 5: New Features

**Goal**: Expose API capabilities not currently available in the plugin.

| Task | Issue | File | Description |
|------|-------|------|-------------|
| 5.1 | #11 | Actions.xml | Add Away On/Off actions for `heatmiserNeostat` |
| 5.2 | #11 | plugin.py | Implement `setAway` / `clearAway` callbacks using `AWAY_ON`/`AWAY_OFF` |
| 5.3 | #11 | Actions.xml | Add Holiday mode action with date picker |
| 5.4 | #11 | plugin.py | Implement `setHoliday` / `cancelHoliday` callbacks |
| 5.5 | #11 | Actions.xml | Add Cancel Hold action |
| 5.6 | #11 | plugin.py | Implement `cancelHold` callback using `CANCEL_HOLD_ALL` |
| 5.7 | #11 | Actions.xml, plugin.py | Add Boost On/Off actions for NeoPlug timeclocks |

**Commit message**: `Add Away, Holiday, Cancel Hold, and Boost actions`

---

## Phase 6: Documentation & CLAUDE.md Update

**Goal**: Update documentation to reflect all changes.

| Task | Issue | File | Description |
|------|-------|------|-------------|
| 6.1 | - | CLAUDE.md | Update to reflect WSS support, new actions, API changes |
| 6.2 | - | CLAUDE.md | Update communication protocol section (WSS + legacy) |
| 6.3 | - | CLAUDE.md | Update available actions table |
| 6.4 | - | CLAUDE.md | Update version to 2026.0.1 |

**Commit message**: `Update documentation for v2026.0.1`

---

## Execution Notes

- **Phase 1-2** can be done without a live NeoHub (pure code fixes)
- **Phase 3** needs testing against a NeoHub to verify field name differences
- **Phase 4** is the riskiest change - consider a feature branch
- **Phase 5** is independent of Phase 4 (works on either TCP or WSS)
- Close GitHub issues as each phase completes
- Update Info.plist version after Phase 5: `2026.0.1`
