# 🧊 CubeCLI — Project Blueprint & Status (`GEMINI.md`)

This document serves as a comprehensive developer reference, architectural spec, database schema map, and state-of-progress tracker for the **CubeCLI** terminal speedcubing timer. It is designed to preserve memory and context across sessions.

---

## 🗺️ Progress & Roadmap

| Phase / Scaffold | Status | Features Completed |
|---|---|---|
| **Scaffold & CI** | ✅ Complete | Hatchling setup, Ruff/Black formatting, Mypy check, 3-OS GitHub Actions CI. |
| **Phase 1: Core Timer** | ✅ Complete | `PrecisionTimer` (microseconds), `TimerState` machine, hold-SPACE logic, WCA basic stats (Mo3/Ao5/Ao12), SQLite CRUD, core UI widgets. |
| **Phase 2: 3x3 Preview** | ✅ Complete | Mathematically correct 3x3 simulator, ANSI color-coded Rich unfolded net widget, responsive auto-hide for non-3x3. |
| **Phase 3: Charts & Stats** | ✅ Complete | Rolling stats (Ao50, Ao100), session/all-time record queries, unified `StatsScreen` with `textual-plot` braille graph (Ao5 trend line overlay). |
| **Phase 4: OLL/PLL Training** | ✅ Complete | OLL/PLL trainers, case databases, trigger ASCII diagrams, case picker, SM-2 spaced repetition, per-case stats. |
| **Phase 5: Power Features** | ⏳ Planned | Multi-puzzle support, BLD/FMC modes, CFOP split timing, metronome, sound alerts. |
| **Phase 6: Import/Export** | ⏳ Planned | csTimer JSON / TwistyTimer CSV imports, full CSV/JSON exports, theme engine. |
| **Phase 7: Smart Cube** | ⏳ Planned | Bleak BLE integration, GAN/MoYu smart cube protocol decoding, TPS analysis. |

---

## 🏗️ Architecture & File Structure

```
CubeCLI/
├── cubecli/
│   ├── core/
│   │   ├── timer.py          # PrecisionTimer, TimerState enum, format_time helper
│   │   ├── scramble.py       # pyTwistyScrambler wrapper + fallback scramble generator
│   │   ├── stats.py          # WCA stats engine (trimmed means, rolling averages, best average finder)
│   │   └── cube_sim.py       # 3x3 Rubik's Cube state simulator (moves: U/D/F/B/L/R with '/2)
│   ├── data/
│   │   ├── models.py         # Solve + Session dataclasses (effective_ms, display_time)
│   │   └── db.py             # SQLite WAL connection manager and CRUD operations
│   ├── ui/
│   │   ├── app.py            # Root Textual application (CubeCLIApp)
│   │   ├── app.tcss          # Global styling, layout grids, timer state color classes
│   │   ├── screens/
│   │   │   ├── timer_screen.py  # Main timer screen (SPACE repeat release detector, hints)
│   │   │   └── stats_screen.py  # Advanced dashboard (tables, textual-plot widget, recent solves list)
│   │   └── widgets/
│   │       ├── cube_preview.py  # ANSI 2D unfolded cross net cube renderer
│   │       ├── timer_display.py # Large digital timer display with state-color classes
│   │       ├── scramble_panel.py# Wrap-safe scramble string displaying panel
│   │       ├── stats_panel.py   # Rolling averages sidebar widget
│   │       └── solve_list.py     # Session history list with braille sparkline
│   ├── config.py             # Config dataclass persisted to ~/.cubecli/config.json
│   └── __init__.py           # Package versioning (0.1.0)
├── tests/
│   ├── test_timer.py         # Timer formatting tests
│   ├── test_scramble.py      # Scramble generation tests
│   ├── test_stats.py         # WCA stats and rolling average tests
│   ├── test_cube_sim.py      # Cube simulator tests (sexy move, T-perm, move parser)
│   └── test_package.py       # Import and package version formatting tests
└── pyproject.toml            # Hatchling build system, dev dependencies, Ruff, Black, Mypy configuration
```

---

## 💾 Database Schema (SQLite in WAL Mode)

Stored locally at `~/.cubecli/solves.db` with `PRAGMA foreign_keys=ON`.

### `sessions`
Tracks practice groups (e.g. "Default 3x3", "BLD session").
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `name` (TEXT NOT NULL)
- `puzzle` (TEXT NOT NULL DEFAULT '3x3')
- `created_at` (REAL NOT NULL)

### `solves`
Tracks individual solve runs linked to a session.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `session_id` (INTEGER REFERENCES sessions(id) ON DELETE CASCADE)
- `time_ms` (INTEGER NOT NULL) — raw elapsed solve time
- `scramble` (TEXT NOT NULL) — scramble string used
- `puzzle` (TEXT NOT NULL DEFAULT '3x3')
- `penalty` (TEXT) — `NULL` (clean), `'+2'` (plus two), or `'DNF'` (did not finish)
- `notes` (TEXT NOT NULL DEFAULT '') — user notes
- `timestamp` (REAL NOT NULL) — Unix epoch solve completion time

---

## ⚙️ Design Patterns & Best Practices

1. **State Machine Timer**:
   - `TimerState` controls display styling.
   - Textual doesn't catch key-releases reliably. Detection is done via key auto-repeat: a `SPACE` event transitions state to `HOLDING`. Every repeated `SPACE` resets a `150ms` one-shot timer (`_release_timer`). If the timer fires, it denotes key release: transition to `READY` / `RUNNING`.

2. **Cube Sim Portability**:
   - Ported from `pglass/cube` mathematically verified permutation tables.
   - Converts 2D `[row][col]` face stickers to a flat 9-sticker layout (`row * 3 + col`) viewed from outside looking in.
   - Validated against Group Theory orders: `order(R U) == 105`, `order(sexy move) == 6`, `order(T-perm) == 2`, `order(Sune) == 6`.

3. **Plot and Axis Formatter**:
   - Uses `textual-plot`'s `PlotWidget` in `HiResMode.BRAILLE`.
   - Formats solve times on the y-axis using `DurationFormatter` and x-axis using `NumericAxisFormatter`.
   - Individual solves are plotted as a scatter plot series, and rolling Ao5 is plotted as a line overlay. DNF solves are excluded from coordinates.

4. **Thread Safety**:
   - Scrambles are generated in a background thread using `@work(thread=True)`.
   - Results are dispatched back to the UI thread using `self.app.call_from_thread(...)` to prevent main loop hangs.

---

## ⚡ Next Phase Guidance (Phase 5: Power Features)

Phase 5 introduces advanced tools for power users. To prepare:
1. **Multi-Puzzle Support**:
   - Extend screens to fully customize scramble length and puzzle display settings for non-3x3 puzzles (2x2, 4x4, 5x5, Pyraminx, Megaminx, Skewb, Square-1, Clock).
2. **BLD & FMC Modes**:
   - Blindfolded (BLD) mode: Add memo/solve split timer. Memo time is tracked when pressing space, and solve time starts automatically until space is pressed again.
   - Fewest Moves Challenge (FMC) mode: Add a 1-hour countdown timer, text editor for inserting solution, and verification tool to count solution moves.
3. **CFOP Split Timing**:
   - Add optional sub-phase triggers (Cross, F2L, OLL, PLL) by tapping a split key (e.g. `Enter` or `s`) during a solve run.
4. **Metronome & Sound Alerts**:
   - Implement audio alerts for target TPS, start/stop sound effects, and configurable metronome frequency for pacing.
