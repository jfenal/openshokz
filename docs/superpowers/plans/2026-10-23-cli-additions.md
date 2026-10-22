# CLI Additions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the openshokz CLI with named custom presets, a preset list command, and a local state file — prerequisites for the GTK4 app and GNOME Shell Extension.

**Architecture:** Three additions to `shokz_config.py` and `protocol.py`: (1) read/write `~/.config/openshokz/presets.json` for custom EQ presets, (2) a new `eq list --json` subcommand, (3) `openshokz eq "<Name>"` lookup by name, (4) write `~/.config/openshokz/state.json` after every successful `eq` apply.

**Tech Stack:** Python 3.11+, stdlib only (`json`, `pathlib`), existing `shokz_config.py` patterns.

**Spec:** `docs/superpowers/specs/2026-10-23-gnome-ui-design.md` — sections "Local preset storage", "CLI additions needed before UI", "Active preset state".

## Global Constraints

- Max 3 custom presets in `presets.json`
- Band values: 7 signed integers, each −12 to +12
- `presets.json` and `state.json` live in `~/.config/openshokz/`
- `eq list --json` output format exactly as in spec (see Task 2)
- `openshokz eq "<Name>"` accepts both built-in slug (`standard`, `vocal`) and custom preset names from `presets.json`
- State file written only after successful headset acknowledgement (`00 00 00 00`)
- All existing CLI tests must continue to pass

## Review Focus

- **Preset file missing on first run** — `eq list --json` and `eq "<Name>"` must work with no `presets.json`; return empty custom list / raise `ShokzError` with "Unknown preset" respectively.
- **3-preset cap** — adding a 4th custom preset via `eq preset add` must fail with a clear error before connecting to the headset.
- **Band value out of range** — `eq custom` with a band > 12 or < −12 must fail with a clear error, not silently clamp.
- **State file written atomically** — a crash mid-write must not leave a corrupt `state.json` (write to `.tmp`, then rename).
- **Named preset with same name as builtin slug** — e.g. a custom preset named "standard" — the built-in takes precedence; document this in the error or handle explicitly.

---

### Task 1: Config directory and preset file helpers

**Files:**
- Modify: `shokz_config.py` (add `_config_dir()`, `_load_presets()`, `_save_presets()`, `_load_state()`, `_save_state()`)
- Modify: `tests/test_protocol.py` (add `TestPresetStorage` class)

**Interfaces:**
- Produces:
  - `_config_dir() -> Path` — returns `~/.config/openshokz`, creating it if absent
  - `_load_presets() -> list[dict[str, object]]` — reads `presets.json`; returns `[]` if absent
  - `_save_presets(presets: list[dict[str, object]]) -> None` — atomic write
  - `_load_state() -> dict[str, str]` — reads `state.json`; returns `{}` if absent
  - `_save_state(active_eq: str) -> None` — atomic write via `.tmp` + rename

- [ ] **Step 1: Write failing tests**

```python
class TestPresetStorage:
    def test_load_presets_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        assert _load_presets() == []

    def test_save_and_load_presets(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        presets = [{"name": "My Bass", "bands": [4, 0, 0, 0, 0, 0, 0]}]
        _save_presets(presets)
        assert _load_presets() == presets

    def test_save_state_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        _save_state("vocal")
        assert _load_state()["active_eq"] == "vocal"

    def test_save_state_atomic(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        _save_state("standard")
        assert not (_config_dir() / "state.json.tmp").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_protocol.py::TestPresetStorage -v`
Expected: FAIL (names not defined)

- [ ] **Step 3: Implement helpers in `shokz_config.py`**

`_config_dir()` — `Path.home() / ".config" / "openshokz"`, `mkdir(parents=True, exist_ok=True)`.
`_load_presets()` — `json.loads(path.read_text())` if path exists, else `[]`.
`_save_presets()` — write via `.tmp` file then `rename`.
`_load_state()` — same pattern, returns `{}` on missing.
`_save_state(active_eq)` — writes `{"active_eq": active_eq, "updated": datetime.now().isoformat()}` atomically.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_protocol.py::TestPresetStorage -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add shokz_config.py tests/test_protocol.py
git commit -m "feat: add config dir and preset/state file helpers"
```

---

### Task 2: `eq list --json` subcommand

**Files:**
- Modify: `shokz_config.py` — add `cmd_eq_list(model)` and wire into `main()`
- Modify: `tests/test_protocol.py` — add `TestEqList`

**Interfaces:**
- Consumes: `_load_presets()` from Task 1, `EQ_PRESETS` from model YAML
- Produces: `cmd_eq_list(model: ModelData) -> None` — prints JSON to stdout, no headset connection needed

- [ ] **Step 1: Write failing tests**

```python
class TestEqList:
    def test_list_builtin_only(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        model = _coerce_model(yaml.safe_load(_MINIMAL_YAML))
        cmd_eq_list(model)
        out = json.loads(capsys.readouterr().out)
        assert len(out) == 2
        assert out[0] == {"name": "Standard", "builtin": True, "arg": "standard"}
        assert out[1] == {"name": "Vocal Booster", "builtin": True, "arg": "vocal"}

    def test_list_includes_custom(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        _save_presets([{"name": "My Bass", "bands": [4, 0, 0, 0, 0, 0, 0]}])
        model = _coerce_model(yaml.safe_load(_MINIMAL_YAML))
        cmd_eq_list(model)
        out = json.loads(capsys.readouterr().out)
        assert out[2] == {"name": "My Bass", "builtin": False, "arg": "My Bass"}
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_protocol.py::TestEqList -v`
Expected: FAIL

- [ ] **Step 3: Implement `cmd_eq_list(model)`**

Build list from `model["eq"]["presets"]` (builtin=True, arg=preset key) then append custom from `_load_presets()` (builtin=False, arg=preset name). Print with `json.dumps(result, indent=2)`. Wire into `main()`: `elif cmd == "eq" and len(args) >= 2 and args[1] == "list": cmd_eq_list(model)`.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_protocol.py::TestEqList -v`
Expected: 2 PASS

- [ ] **Step 5: Smoke test without headset**

Run: `python3 -I shokz_config.py eq list --json`
Expected: JSON array with Standard, Vocal Booster (no headset needed)

- [ ] **Step 6: Commit**

```bash
git add shokz_config.py tests/test_protocol.py
git commit -m "feat: add eq list --json subcommand"
```

---

### Task 3: Named preset lookup and state file on apply

**Files:**
- Modify: `shokz_config.py` — extend `cmd_eq()` to accept preset name string, write state on success
- Modify: `tests/test_protocol.py` — add `TestNamedPreset`

**Interfaces:**
- Consumes: `_load_presets()`, `_save_state()` from Task 1
- Produces: `cmd_eq(mac, model, channel, preset_name, custom_bands)` writes `state.json` after `00 00 00 00` ACK

- [ ] **Step 1: Write failing tests**

```python
class TestNamedPreset:
    def test_named_builtin_resolves(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        model = _coerce_model(yaml.safe_load(_MINIMAL_YAML))
        preset_id, bands = _resolve_preset_name("standard", model)
        assert preset_id == 1
        assert bands == [0, 0, 0, 0, 0, 0, 0]

    def test_named_custom_resolves(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        _save_presets([{"name": "My Bass", "bands": [4, 0, 0, 0, 0, 0, 0]}])
        model = _coerce_model(yaml.safe_load(_MINIMAL_YAML))
        preset_id, bands = _resolve_preset_name("My Bass", model)
        assert preset_id == 1  # custom uses preset_id 1 (Standard slot)
        assert bands == [4, 0, 0, 0, 0, 0, 0]

    def test_unknown_preset_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        model = _coerce_model(yaml.safe_load(_MINIMAL_YAML))
        with pytest.raises(ShokzError, match="Unknown preset"):
            _resolve_preset_name("doesnotexist", model)

    def test_band_out_of_range_raises(self):
        with pytest.raises(ShokzError, match="band value"):
            _validate_bands([13, 0, 0, 0, 0, 0, 0])
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_protocol.py::TestNamedPreset -v`
Expected: FAIL

- [ ] **Step 3: Implement `_resolve_preset_name()` and `_validate_bands()`**

`_resolve_preset_name(name, model)` — check builtin presets first (exact match on key or label), then `_load_presets()` by name; raise `ShokzError("Unknown preset '...'")` if not found. Returns `(preset_id, bands)`.

`_validate_bands(bands)` — raise `ShokzError("band value N out of range −12..12")` if any band outside [−12, 12].

Extend `cmd_eq()`: when `preset_name` is a string not in `{"standard","vocal","custom"}`, call `_resolve_preset_name()`. After successful headset ACK (`resp == b"\x00\x00\x00\x00"`), call `_save_state(preset_name)`. Call `_validate_bands()` before sending.

Wire into `main()`: single-token `openshokz eq "My Bass"` → `cmd_eq(..., preset_name="My Bass")`.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_protocol.py::TestNamedPreset -v`
Expected: 4 PASS

- [ ] **Step 5: Full test suite**

Run: `python3 -m pytest tests/ -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add shokz_config.py tests/test_protocol.py
git commit -m "feat: named preset lookup and state file write on eq apply"
```

---

### Task 4: Custom preset management (`eq preset add/delete`)

**Files:**
- Modify: `shokz_config.py` — add `cmd_preset_add()`, `cmd_preset_delete()`, wire into `main()`
- Modify: `tests/test_protocol.py` — add `TestPresetManagement`

**Interfaces:**
- Consumes: `_load_presets()`, `_save_presets()`, `_validate_bands()` from Tasks 1 & 3
- Produces:
  - `openshokz eq preset add "<Name>" b0 b1 b2 b3 b4 b5 b6` — save custom preset (max 3)
  - `openshokz eq preset delete "<Name>"` — remove custom preset

- [ ] **Step 1: Write failing tests**

```python
class TestPresetManagement:
    def test_add_preset(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        cmd_preset_add("My Bass", [4, 0, 0, 0, 0, 0, 0])
        assert _load_presets()[0]["name"] == "My Bass"

    def test_add_fourth_preset_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        _save_presets([{"name": f"P{i}", "bands": [0] * 7} for i in range(3)])
        with pytest.raises(ShokzError, match="maximum 3"):
            cmd_preset_add("P4", [0] * 7)

    def test_delete_preset(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        _save_presets([{"name": "My Bass", "bands": [4, 0, 0, 0, 0, 0, 0]}])
        cmd_preset_delete("My Bass")
        assert _load_presets() == []

    def test_delete_nonexistent_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with pytest.raises(ShokzError, match="not found"):
            cmd_preset_delete("Ghost")
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_protocol.py::TestPresetManagement -v`
Expected: FAIL

- [ ] **Step 3: Implement `cmd_preset_add()` and `cmd_preset_delete()`**

`cmd_preset_add(name, bands)` — load presets, raise if len ≥ 3, validate bands, append, save. No headset connection.

`cmd_preset_delete(name)` — load presets, find by name (raise if not found), remove, save. No headset connection.

Wire into `main()`: `openshokz eq preset add "<Name>" b0..b6` and `openshokz eq preset delete "<Name>"`.

- [ ] **Step 4: Run all tests**

Run: `python3 -m pytest tests/ -q`
Expected: all pass

- [ ] **Step 5: Commit and push**

```bash
git add shokz_config.py tests/test_protocol.py
git commit -m "feat: custom preset add/delete management"
git push
```
