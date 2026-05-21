# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
python pomodoro.py
```

No build step required. Dependencies (install if missing):

```bash
pip install Pillow pystray
```

`winsound` is Windows-built-in and requires no install. The app is Windows-only due to this dependency.

## Architecture

Single-file app: all logic lives in [pomodoro.py](pomodoro.py) (~321 lines).

**One class: `PomodoroApp`** wraps everything:
- `_build_ui` — constructs Tkinter widgets (mode buttons, task input, canvas timer ring, stats)
- `toggle` / `reset` / `_tick` / `_on_complete` — timer state machine
- `_update_display` — syncs canvas arc, label, button states, and window title each tick
- `_start_tray` / `minimize_to_tray` — pystray system tray integration (closing window minimizes instead of quitting)
- `load_data` / `save_data` — reads/writes `pomodoro_data.json` for daily + total pomodoro counts

**Timer modes** (`DURATIONS` dict): `work` 25 min → after 4 sessions → `long_break` 15 min; breaks auto-return to `work`.

**Data file** (`pomodoro_data.json`, gitignored): `{ "today": "YYYY-MM-DD", "count": N, "total": N }`. Daily count resets automatically when the date changes.

**Color scheme**: Catppuccin Mocha palette — pink for work, green for short break, cyan for long break. Constants defined in the `COLORS` dict at the top of the file.

**UI language**: Chinese (simplified). The task placeholder is "今天在做什么？", mode labels are "专注时间", "短暂休息", "长休息".

## No Tests or Linter

There is no test suite or linting config. Manual testing by running the app is the only verification path.
