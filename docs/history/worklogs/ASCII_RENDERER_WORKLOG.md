# ASCII Renderer Rewrite — TerminalChart Worklog

## Context

The old `ascii_renderer.py` produced one-line sparklines for
convergence/DOS/bands/trajectory data.  This was inadequate for agent use.
The rewrite provides a proper 2D terminal chart with axes, ticks, data curves,
and reference lines.

---

## Phase 0: Plotext Study (complete before implementation)

Studied `plotext` source at `/repo_research/plotext/plotext/`.  Key takeaways:

| Concern | Plotext approach | Our approach |
|---------|-----------------|--------------|
| Canvas | 2D char array | Same |
| Data→grid | `floor(0.5 + (bins-1) * (v-min)/(max-min))` | `round((v-min)/(max-min) * (plot_w-1))` |
| Line drawing | linspace interpolation | Same (not Bresenham) |
| Flat line | expand `[0.5v, 1.5v]` or `[-1,1]` | `[v±50%]` or `[v±1]` |
| Downsampling | None (dedup grid cells) | Min/max envelope when n_pts > 2×plot_w |
| Ticks | `distinguishing_digit` precision | Auto-detect via span/min_diff |
| HD chars | Braille/block | Not used (ASCII + `●` `·` `○` `×` `+`) |
| Colors | ANSI codes | Not used |

---

## Implementation Log

### Step 1 — Worklog created

### Step 2 — `src/qmatsuite/mcp/renderers/terminal_chart.py` created
- `TerminalChart` class: add_series, add_hline, add_vline, set_xlabel, set_ylabel, render
- `_compute_ticks`, `_format_ticks`, `_to_col`, `_to_row`, `_draw_line` helpers
- Dense data handling: envelope when n_pts > 2×plot_w
- Edge cases: empty (→ "No data"), flat Y (±50% or ±1), NaN/Inf filtered

### Step 3 — `ascii_renderer.py` updated
- Added `render_bundle_to_ascii()` using TerminalChart
- Updated `render_bundle_ascii` dispatch: convergence/dos/bands/trajectory → TerminalChart
- Kept: `_sparkline`, `_unicode_bar`, `_render_scf_digest`, `_render_field3d`, `_render_generic`

### Step 4 — `renderers/__init__.py` updated
- Exports: `TerminalChart`, `render_bundle_ascii`, `render_bundle_to_ascii`

### Step 5 — `tests/mcp/test_terminal_chart.py` created
- 13 TerminalChart unit tests + 4 integration tests

### Step 6 — `tests/mcp/test_phase2a.py` updated
- 4 TestAsciiRenderer tests updated (convergence/dos/bands/trajectory)
- 3 TestPlotAnalysis tests updated (convergence/dos/bands happy paths)

### Step 6 (cont.) — `tests/mcp/test_stage5.py` also updated
- `test_list_and_plot_convergence`: removed old "=== Convergence ===" / "Sparkline:" checks

### Step 7 — Full test suite run
- Result: **6233 passed, 4 skipped, 0 failed** ✓
