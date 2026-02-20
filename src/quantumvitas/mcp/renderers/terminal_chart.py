"""Pure-stdlib 2D terminal chart for QMatSuite MCP ASCII renderer.

Produces fixed-width (~80 cols) text charts with axes, ticks, data curves,
and reference lines.  No external dependencies.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Optional


# ---------------------------------------------------------------------------
# Marker and line characters
# ---------------------------------------------------------------------------

_MARKERS = ["●", "○", "×", "+"]
_CONNECT_CHAR = "·"  # middle dot for interpolated line segments


# ---------------------------------------------------------------------------
# Internal data holders
# ---------------------------------------------------------------------------

class _Series:
    __slots__ = ("x", "y", "label", "marker_char")

    def __init__(self, x: list[float], y: list[float], label: str, marker_char: str):
        self.x = x
        self.y = y
        self.label = label
        self.marker_char = marker_char


class _HLine:
    __slots__ = ("y", "label", "char")

    def __init__(self, y: float, label: str, char: str):
        self.y = y
        self.label = label
        self.char = char


class _VLine:
    __slots__ = ("x", "label", "char")

    def __init__(self, x: float, label: str, char: str):
        self.x = x
        self.label = label
        self.char = char


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def _compute_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    """Evenly spaced ticks from lo to hi, inclusive."""
    if n <= 1:
        return [(lo + hi) / 2]
    return [lo + i * (hi - lo) / (n - 1) for i in range(n)]


def _format_ticks(ticks: list[float]) -> list[str]:
    """Format tick values with auto-detected precision.

    Uses scientific notation for very large (>1e4) or very small (<1e-3)
    magnitudes.  Otherwise chooses enough decimal places to distinguish
    adjacent ticks.
    """
    if not ticks:
        return []

    abs_max = max(abs(t) for t in ticks)
    nonzero = [abs(t) for t in ticks if t != 0]

    use_sci = abs_max >= 1e4 or (nonzero and min(nonzero) < 1e-3 and abs_max < 1.0)

    if use_sci:
        # Find precision to distinguish adjacent formatted ticks
        prec = 2
        if len(ticks) > 1:
            diffs = [abs(ticks[i + 1] - ticks[i]) for i in range(len(ticks) - 1)
                     if ticks[i + 1] != ticks[i]]
            if diffs:
                min_diff = min(diffs)
                if min_diff > 0:
                    prec = max(0, -int(math.floor(math.log10(min_diff))) + 1)
                    prec = min(prec, 4)
        return [f"{t:.{prec}e}" for t in ticks]

    # Normal range: decimal places from span between adjacent ticks
    span = max(ticks) - min(ticks)
    if span == 0:
        if abs_max == 0:
            return ["0"] * len(ticks)
        prec = max(0, -int(math.floor(math.log10(abs_max))) + 2)
        prec = min(prec, 6)
    else:
        min_step = span / max(len(ticks) - 1, 1)
        if min_step >= 1:
            prec = 0
        else:
            prec = max(0, -int(math.floor(math.log10(min_step))) + 1)
        prec = min(prec, 6)

    return [f"{t:.{prec}f}" for t in ticks]


def _to_col(x: float, x_min: float, x_max: float, plot_w: int) -> int:
    """Map a data x value to a canvas column index."""
    if x_max == x_min:
        return plot_w // 2
    return max(0, min(plot_w - 1, round((x - x_min) / (x_max - x_min) * (plot_w - 1))))


def _to_row(y: float, y_min: float, y_max: float, plot_h: int) -> int:
    """Map a data y value to a canvas row index (row 0 = top = y_max)."""
    if y_max == y_min:
        return plot_h // 2
    return max(0, min(plot_h - 1, round((y_max - y) / (y_max - y_min) * (plot_h - 1))))


def _draw_line(
    canvas: list[list[str]],
    r0: int, c0: int,
    r1: int, c1: int,
    char: str,
    plot_h: int,
    plot_w: int,
) -> None:
    """Draw a line segment using linspace interpolation."""
    steps = max(abs(c1 - c0), abs(r1 - r0), 1)
    for i in range(steps + 1):
        c = round(c0 + i * (c1 - c0) / steps)
        r = round(r0 + i * (r1 - r0) / steps)
        if 0 <= r < plot_h and 0 <= c < plot_w:
            canvas[r][c] = char


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class TerminalChart:
    """Pure-stdlib 2D terminal chart.

    Usage::

        chart = TerminalChart(width=78, height=16, title="My Chart")
        chart.add_series(x_vals, y_vals, label="Series 1")
        chart.add_hline(0.0, label="zero")
        chart.set_xlabel("X Label")
        chart.set_ylabel("Y Label")
        print(chart.render())
    """

    def __init__(self, width: int = 78, height: int = 16, title: str = ""):
        self._width = width
        self._height = height
        self._title = title
        self._series: list[_Series] = []
        self._hlines: list[_HLine] = []
        self._vlines: list[_VLine] = []
        self._xlabel = ""
        self._ylabel = ""

    # ------------------------------------------------------------------
    # Builder methods
    # ------------------------------------------------------------------

    def add_series(
        self,
        x: list[float],
        y: list[float],
        label: str = "",
        marker: str = "",
    ) -> None:
        """Add a data series.  Non-finite (NaN/Inf) pairs are silently dropped."""
        m = marker or _MARKERS[len(self._series) % len(_MARKERS)]
        pairs = [(xi, yi) for xi, yi in zip(x, y)
                 if math.isfinite(xi) and math.isfinite(yi)]
        if pairs:
            xs, ys = zip(*pairs)
            self._series.append(_Series(list(xs), list(ys), label, m))

    def add_hline(self, y: float, label: str = "", char: str = "─") -> None:
        """Add a horizontal reference line at the given y value."""
        if math.isfinite(y):
            self._hlines.append(_HLine(y, label, char))

    def add_vline(self, x: float, label: str = "", char: str = "│") -> None:
        """Add a vertical reference line at the given x value."""
        if math.isfinite(x):
            self._vlines.append(_VLine(x, label, char))

    def set_xlabel(self, label: str) -> None:
        self._xlabel = label

    def set_ylabel(self, label: str) -> None:
        self._ylabel = label

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self) -> str:
        """Render the chart to a multi-line string."""
        # Collect finite data
        all_x: list[float] = []
        all_y: list[float] = []
        for s in self._series:
            all_x.extend(s.x)
            all_y.extend(s.y)

        if not all_x:
            return "No data"

        # Data ranges
        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)

        # Expand ranges to include reference lines
        for hl in self._hlines:
            y_min = min(y_min, hl.y)
            y_max = max(y_max, hl.y)
        for vl in self._vlines:
            x_min = min(x_min, vl.x)
            x_max = max(x_max, vl.x)

        # Handle flat / single-point data
        if y_max == y_min:
            margin = abs(y_min) * 0.5 if y_min != 0 else 1.0
            y_min -= margin
            y_max += margin
        if x_max == x_min:
            margin = abs(x_min) * 0.5 if x_min != 0 else 1.0
            x_min -= margin
            x_max += margin

        # Y-tick labels → determine y_label_width
        n_yticks = 5
        y_ticks = _compute_ticks(y_min, y_max, n_yticks)
        y_tick_labels = _format_ticks(y_ticks)
        y_label_width = min(max(len(lb) for lb in y_tick_labels), 12)

        # Layout dimensions
        # Each data row: y_label_width + "┤"/"│" + " " + plot_w = self._width
        plot_w = self._width - y_label_width - 2
        plot_h = self._height
        if plot_w < 4:
            plot_w = 4

        # Create blank canvas
        canvas: list[list[str]] = [[" "] * plot_w for _ in range(plot_h)]

        # Draw horizontal reference lines
        for hl in self._hlines:
            r = _to_row(hl.y, y_min, y_max, plot_h)
            for c in range(plot_w):
                canvas[r][c] = hl.char

        # Draw vertical reference lines
        for vl in self._vlines:
            c = _to_col(vl.x, x_min, x_max, plot_w)
            for r in range(plot_h):
                if canvas[r][c] == " ":
                    canvas[r][c] = vl.char

        # Draw each series
        for s in self._series:
            pairs = sorted(zip(s.x, s.y), key=lambda p: p[0])
            cols = [_to_col(xi, x_min, x_max, plot_w) for xi, _ in pairs]
            rows = [_to_row(yi, y_min, y_max, plot_h) for _, yi in pairs]
            n_pts = len(pairs)

            if n_pts > 2 * plot_w:
                # Dense data: draw min/max envelope per column
                col_to_rows: dict[int, list[int]] = defaultdict(list)
                for col, row in zip(cols, rows):
                    col_to_rows[col].append(row)
                for col, col_rows in sorted(col_to_rows.items()):
                    r_lo = min(col_rows)
                    r_hi = max(col_rows)
                    for r in range(r_lo, r_hi + 1):
                        canvas[r][col] = "│" if r_lo != r_hi else s.marker_char
            else:
                # Sparse data: line-connect adjacent points, then place markers
                for i in range(n_pts - 1):
                    c0, r0 = cols[i], rows[i]
                    c1, r1 = cols[i + 1], rows[i + 1]
                    if (c0, r0) != (c1, r1):
                        _draw_line(canvas, r0, c0, r1, c1, _CONNECT_CHAR, plot_h, plot_w)
                # Place markers on top of connection lines
                for col, row in zip(cols, rows):
                    canvas[row][col] = s.marker_char

        # X-tick computation
        n_xticks = min(6, max(2, plot_w // 10))
        x_ticks = _compute_ticks(x_min, x_max, n_xticks)
        x_tick_labels = _format_ticks(x_ticks)
        x_tick_cols = [_to_col(xv, x_min, x_max, plot_w) for xv in x_ticks]

        # Y-tick row mapping: row index → label string
        y_tick_row_map: dict[int, str] = {}
        for yv, lb in zip(y_ticks, y_tick_labels):
            row = _to_row(yv, y_min, y_max, plot_h)
            y_tick_row_map[row] = lb

        # Assemble output lines
        output: list[str] = []

        # Optional title
        if self._title:
            output.append(self._title.center(self._width))

        # Optional Y-axis label (shown as a one-line annotation above data)
        if self._ylabel:
            output.append(self._ylabel[:self._width])

        # Data rows (top = row 0 = y_max)
        for r in range(plot_h):
            if r in y_tick_row_map:
                raw_label = y_tick_row_map[r]
                label = raw_label.rjust(y_label_width)
                sep = "┤"
            else:
                label = " " * y_label_width
                sep = "│"
            output.append(label + sep + " " + "".join(canvas[r]))

        # Bottom border
        output.append(" " * y_label_width + "└" + "─" * plot_w)

        # X-tick labels row
        xtick_row = [" "] * (y_label_width + 1 + plot_w)
        offset = y_label_width + 1  # canvas starts at this index
        for col, lb in zip(x_tick_cols, x_tick_labels):
            start = offset + col - len(lb) // 2
            for ci, ch in enumerate(lb):
                idx = start + ci
                if 0 <= idx < len(xtick_row):
                    xtick_row[idx] = ch
        output.append("".join(xtick_row).rstrip())

        # X-axis label
        if self._xlabel:
            output.append(self._xlabel.center(self._width))

        return "\n".join(output)
