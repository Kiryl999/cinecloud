# /// script
# requires-python = ">=3.12"
# dependencies = ["matplotlib==3.10.*"]
# ///
"""Compares measurement series from loadtest/run.py in charts and tables.

    uv run loadtest/report.py baseline "seatmap-once=Sitzplan einmal" [--out DIR]

Each argument names a series in loadtest/results/, optionally with the label
the charts give it. Writes PDF charts (for the thesis), PNG copies, the numbers
behind them as CSV, Markdown and a LaTeX table (booktabs), and index.html,
which links every run's k6 report.
"""

import argparse
import csv
import gzip
import html
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
BUCKET = 30  # seconds per point of the timelines

# categorical slots in fixed order (validated: CVD and contrast)
COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]
INK, INK_2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
ENDPOINTS = {
    "cinema": "Kino",
    "showtimes": "Spielplan",
    "showtime": "Vorstellung",
    "seat stream": "Sitzplan-Stream",
    "hold": "Reservieren",
    "booking": "Buchen",
}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
    "font.size": 8.5,
    "axes.titlesize": 9,
    "axes.titleweight": "semibold",
    "axes.titlelocation": "left",
    "axes.titlecolor": INK,
    "axes.labelcolor": INK_2,
    "axes.edgecolor": AXIS,
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "xtick.color": AXIS,
    "ytick.color": AXIS,
    "xtick.labelcolor": INK_2,
    "ytick.labelcolor": INK_2,
    "legend.frameon": False,
    "legend.fontsize": 8.5,
    "lines.solid_capstyle": "round",
    "lines.solid_joinstyle": "round",
    "pdf.fonttype": 42,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})


# --- numbers --------------------------------------------------------------

def de(value: float | None, digits: int = 0) -> str:
    """German number format: 1.234,5"""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "–"
    text = f"{value:,.{digits}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".").replace("-", "−")


def pct(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile, as k6 reports it closely enough."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p * len(ordered)) - 1)]


def median(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return statistics.median(present) if present else None


# --- one run --------------------------------------------------------------

class Run:
    def __init__(self, folder: Path):
        self.folder = folder
        self.meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        summary = folder / "summary.json"  # missing if k6 had to be stopped, see meta note
        self.summary = json.loads(summary.read_text(encoding="utf-8"))["metrics"] if summary.exists() else {}
        self.requests: list[tuple[int, str, float, bool]] = []  # (t, endpoint, ms, expected)
        self.iterations: list[int] = []
        with gzip.open(folder / "k6.csv.gz", "rt", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["group"] in ("::setup", "::teardown"):
                    continue
                if row["metric_name"] == "http_req_duration":
                    self.requests.append((int(row["timestamp"]), row["name"], float(row["metric_value"]),
                                          row["expected_response"] == "true"))
                elif row["metric_name"] == "iterations":
                    self.iterations.append(int(row["timestamp"]))
        self.t0 = min(t for t, *_ in self.requests)

    def prometheus(self, name: str) -> list[tuple[float, dict[str, float]]]:
        """(seconds since the start, {column: value}) per sample."""
        with open(self.folder / "prometheus" / f"{name}.csv", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        return [(int(r.pop("time")) - self.t0, {k: float(v) for k, v in r.items() if v}) for r in rows]

    def backend_cpu(self) -> list[tuple[float, float]]:
        return [(t, sum(v for k, v in cols.items() if k.startswith("pod=backend-")))
                for t, cols in self.prometheus("cpu_by_pod")]

    def ready_pods(self) -> list[tuple[float, float]]:
        return [(t, cols["value"]) for t, cols in self.prometheus("ready_pods") if "value" in cols]

    def window(self, start: float, end: float):
        return [r for r in self.requests if start <= r[0] - self.t0 < end]


def buckets(samples: list[tuple[float, float]], reduce) -> dict[int, float]:
    grouped = defaultdict(list)
    for t, v in samples:
        grouped[int(t // BUCKET) * BUCKET].append(v)
    return {b: reduce(vs) for b, vs in grouped.items() if b >= 0}


# --- the ramp: a whole evening -------------------------------------------

def ramp_peak(run: Run) -> tuple[float, float]:
    """The minutes at full load, see the stages in ramp.js."""
    minutes = float(run.meta["env"].get("PEAK_MINUTES", 5))
    return 540 + 30, 540 + minutes * 60


def ramp_stats(run: Run) -> dict:
    start, end = ramp_peak(run)
    ok = [ms for _, _, ms, expected in run.requests if expected]
    peak = run.window(start, end)
    # each sample averages the 2 minutes before it: only those wholly inside the peak
    cpu = [c for t, c in run.backend_cpu() if start + 120 <= t <= end]
    cpu_seconds = statistics.mean(cpu) * (end - start) if cpu else None
    visitors = sum(1 for t in run.iterations if start <= t - run.t0 < end)
    # the whole test as well: more data, though with the ramps and the scaling in it
    run_cpu_seconds = sum(c for t, c in run.backend_cpu() if t >= 0) * 15
    throttled = [v for t, cols in run.prometheus("throttled_share") if start + 120 <= t <= end
                 for v in cols.values()]
    pods = run.ready_pods()
    minimum = run.meta["autoscaler"]["minReplicas"]
    scaled = next((t for t, n in pods if t >= 0 and n > minimum), None)
    rate = buckets([(r[0] - run.t0, 1) for r in run.requests], len)
    failed_pct = 100 * sum(1 for *_, e in run.requests if not e) / len(run.requests)
    return {
        "requests": len(run.requests),
        "failed_pct": failed_pct,
        "p50": pct(ok, .5), "p95": pct(ok, .95), "p99": pct(ok, .99),
        "peak_p95": pct([ms for _, _, ms, e in peak if e], .95),
        "peak_rps": len(peak) / (end - start),
        "peak_pods": median([n for t, n in pods if start <= t < end]),
        "max_pods": max((n for t, n in pods if t >= 0), default=None),
        "scaled_after_s": scaled,
        "scaled_at_rps": rate.get(int(scaled // BUCKET) * BUCKET, 0) / BUCKET if scaled is not None else None,
        "cpu_ms_per_request": cpu_seconds * 1000 / len(peak) if cpu_seconds and peak else None,
        "cpu_ms_per_visitor": cpu_seconds * 1000 / visitors if cpu_seconds and visitors else None,
        "cpu_ms_per_visitor_run": run_cpu_seconds * 1000 / len(run.iterations),
        "throttled_pct": 100 * statistics.mean(throttled) if throttled else None,
        "dropped_iterations": run.meta["checks"]["dropped_iterations"],
        "cores_elsewhere": run.meta["checks"]["max_cores_elsewhere"],
        # the thresholds of ramp.js, from the raw data
        "passed": pct(ok, .95) < 1000 and failed_pct < 1,
    }


def endpoint_p50(run: Run) -> dict[str, float]:
    """Median per request type while the load is low (minutes 1 to 3 of
    ramp.js): close to what a request costs, before any queueing."""
    per = defaultdict(list)
    for _, name, ms, expected in run.window(60, 180):
        if expected:
            per[name].append(ms)
    return {name: pct(values, .5) for name, values in per.items()}


def timeline(run: Run) -> dict[str, dict[int, float]]:
    requests = [(t - run.t0, ms, e) for t, _, ms, e in run.requests]
    return {
        "rps": buckets([(t, 1) for t, _, _ in requests], lambda vs: len(vs) / BUCKET),
        "p95": buckets([(t, ms) for t, ms, e in requests if e], lambda vs: pct(vs, .95)),
        "pods": buckets(run.ready_pods(), max),
        "cpu": buckets(run.backend_cpu(), statistics.mean),
    }


def median_line(lines: list[dict[int, float]]) -> tuple[list[float], list[float]]:
    keys = sorted({k for line in lines for k in line})
    xs = [k / 60 for k in keys]
    return xs, [median([line.get(k) for line in lines]) for k in keys]


def ms_axis(ax, low: float, high: float) -> None:
    ax.set_yscale("log")
    ticks = [t for t in (5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000)
             if low / 1.5 <= t <= high * 1.5]
    ax.yaxis.set_major_locator(FixedLocator(ticks))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: de(v)))


def chart_ramp_timeline(series: list[tuple[str, list[Run]]], out: Path) -> None:
    panels = [
        ("rps", "Anfragen pro Sekunde", lambda v, _: de(v)),
        ("p95", "p95-Antwortzeit (ms, logarithmisch)", None),
        ("pods", "Backend-Pods (bereit)", lambda v, _: de(v)),
        ("cpu", "CPU-Verbrauch des Backends (Kerne)", lambda v, _: de(v, 1)),
    ]
    fig, axes = plt.subplots(len(panels), 1, figsize=(6.3, 7.6), sharex=True,
                             gridspec_kw={"hspace": 0.45})
    lows, highs = [], []
    for index, (label, runs) in enumerate(series):
        color = COLORS[index]
        lines = [timeline(run) for run in runs]
        for ax, (key, title, fmt) in zip(axes, panels):
            for line in lines:
                xs = sorted(line[key])
                ax.plot([x / 60 for x in xs], [line[key][x] for x in xs], color=color, lw=0.7,
                        alpha=0.3, drawstyle="steps-post" if key == "pods" else "default")
            xs, ys = median_line([line[key] for line in lines])
            ax.plot(xs, ys, color=color, lw=1.6, label=label if key == "rps" else None,
                    drawstyle="steps-post" if key == "pods" else "default")
            if key == "p95":
                values = [v for line in lines for v in line[key].values() if v]
                lows.append(min(values))
                highs.append(max(values))
    start, end = ramp_peak(series[0][1][0])
    for ax, (key, title, fmt) in zip(axes, panels):
        ax.set_title(title)
        ax.axvspan(start / 60, end / 60, color=GRID, alpha=0.45, lw=0, zorder=0)
        if fmt:
            ax.yaxis.set_major_formatter(FuncFormatter(fmt))
    axes[0].text((start + end) / 120, axes[0].get_ylim()[1], "volle Last", ha="center", va="bottom",
                 color=MUTED, fontsize=7.5)
    ms_axis(axes[1], min(lows), max(highs))
    axes[2].yaxis.set_major_locator(FixedLocator(range(0, 6)))
    axes[2].set_ylim(0, max(4, axes[2].get_ylim()[1]))
    axes[-1].set_xlabel("Minuten seit Beginn des Tests\n(dünn: einzelne Läufe, kräftig: Median je Zeitpunkt)")
    axes[-1].xaxis.set_major_formatter(FuncFormatter(lambda v, _: de(v)))
    fig.subplots_adjust(top=0.9)
    if len(series) > 1:
        fig.legend(loc="lower left", bbox_to_anchor=(0.1, 0.935), ncols=len(series))
    save(fig, out / "abend-verlauf")


# one hue, light to dark: the percentiles are ordered (validated as an ordinal ramp)
PERCENTILES = [(.5, "p50 (Median)", "#86b6ef"), (.95, "p95", "#2a78d6"), (.99, "p99", "#104281")]


def chart_percentiles(runs: list[Run], out: Path) -> None:
    """p50, p95 and p99 over the course of the test, the requests of all runs
    of a series pooled per time step."""
    durations, rates, pods = defaultdict(list), defaultdict(list), defaultdict(list)
    for run in runs:
        for t, _, ms, ok in run.requests:
            if ok:
                durations[int((t - run.t0) // BUCKET) * BUCKET].append(ms)
        for b, rate in timeline(run)["rps"].items():
            rates[b].append(rate)
        for b, n in buckets(run.ready_pods(), max).items():
            pods[b].append(n)
    # a percentile needs enough requests behind it, which the last seconds lack
    keys = sorted(k for k in durations if len(durations[k]) >= 300)
    xs = [k / 60 for k in keys]

    fig, axes = plt.subplots(3, 1, figsize=(6.3, 6.4), sharex=True,
                             gridspec_kw={"hspace": 0.5, "height_ratios": [1, 1.7, 0.8]})
    axes[0].plot(xs, [statistics.mean(rates[k]) for k in keys], color=COLORS[0], lw=1.6)
    axes[0].set_title("Anfragen pro Sekunde")
    axes[0].set_ylim(bottom=0)
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda v, _: de(v)))

    values = []
    for p, name, color in PERCENTILES:
        ys = [pct(durations[k], p) for k in keys]
        values += ys
        axes[1].plot(xs, ys, color=color, lw=1.6, label=name)
    axes[1].set_title("Antwortzeit (ms, logarithmisch)")
    ms_axis(axes[1], min(values), max(values))
    # beside the title, clear of the peaks
    axes[1].legend(loc="lower right", bbox_to_anchor=(1, 1), ncols=3, borderaxespad=0.2)

    pod_keys = [k for k in sorted(pods) if keys[0] <= k <= keys[-1]]
    axes[2].plot([k / 60 for k in pod_keys], [statistics.median(pods[k]) for k in pod_keys],
                 color=COLORS[0], lw=1.6, drawstyle="steps-post")
    axes[2].set_title("Backend-Instanzen")
    axes[2].yaxis.set_major_locator(FixedLocator(range(0, 6)))
    axes[2].set_ylim(0, max(4, axes[2].get_ylim()[1]))
    axes[-1].set_xlabel(f"Minuten seit Beginn des Tests (Anfragen aus {len(runs)} Läufen zusammengefasst)")
    axes[-1].xaxis.set_major_formatter(FuncFormatter(lambda v, _: de(v)))
    save(fig, out / f"abend-perzentile-{runs[0].folder.parent.name}")


def chart_dots(series, metrics: list[tuple[str, object]], unit: str, out_name: str, out: Path,
               digits=1) -> None:
    """One dot per run, a short bar at the median - with three runs a bar chart
    would hide the spread. One panel per (title, value of a run)."""
    fig, axes = plt.subplots(len(metrics), 1, figsize=(6.3, (0.75 + 0.42 * len(series)) * len(metrics)),
                             sharex=True, squeeze=False, gridspec_kw={"hspace": 0.9})
    for ax, (title, values_of) in zip(axes[:, 0], metrics):
        base = None
        for index, (label, runs) in enumerate(series):
            y = len(series) - 1 - index
            values = [v for v in (values_of(run) for run in runs) if v is not None]
            if not values:
                continue
            mid = statistics.median(values)
            ax.scatter(values, [y] * len(values), s=26, color=COLORS[index], edgecolor="white",
                       linewidth=1.2, zorder=3)
            ax.plot([mid, mid], [y - 0.22, y + 0.22], color=INK, lw=1.4, zorder=4)
            text = f"{de(mid, digits)} {unit}"
            if base is None:
                base = mid
            elif base:
                change = 100 * (mid / base - 1)
                text += f"  ({'+' if change > 0 else ''}{de(change, 0)} %)"
            ax.text(max(values), y, "   " + text, va="center", color=INK_2, fontsize=8)
        ax.set_yticks(range(len(series)), [label for label, _ in reversed(series)])
        ax.set_ylim(-0.6, len(series) - 0.4)
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", length=0)
        ax.set_title(title)
    axes[-1, 0].set_xlim(left=0, right=axes[-1, 0].get_xlim()[1] * 1.35)
    axes[-1, 0].xaxis.set_major_formatter(FuncFormatter(lambda v, _: de(v, 0 if v >= 10 else 1)))
    axes[-1, 0].set_xlabel("ein Punkt je Lauf, Strich: Median")
    save(fig, out / out_name)


def chart_endpoints(series: list[tuple[str, list[Run]]], out: Path) -> None:
    per_series = []
    for _, runs in series:
        each = [endpoint_p50(run) for run in runs]
        per_series.append({name: median([e.get(name) for e in each]) for name in ENDPOINTS})
    fig, ax = plt.subplots(figsize=(6.3, 0.5 + 0.28 * len(ENDPOINTS) * len(series)))
    height = 0.8 / len(series)
    names = list(ENDPOINTS)
    for index, ((label, _), values) in enumerate(zip(series, per_series)):
        ys = [len(names) - 1 - i + (len(series) - 1) / 2 * height - index * height for i in range(len(names))]
        widths = [values[name] or 0 for name in names]
        ax.barh(ys, widths, height=height * 0.82, color=COLORS[index], label=label)
        for y, w in zip(ys, widths):
            ax.text(w, y, f" {de(w, 1)}", va="center", color=INK_2, fontsize=7.5)
    ax.set_yticks(range(len(names)), [ENDPOINTS[n] for n in reversed(names)])
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, ax.get_xlim()[1] * 1.12)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: de(v)))
    ax.set_xlabel("Median der Antwortzeit bei geringer Last, Minute 1 bis 3 (ms, Median der Läufe)")
    ax.set_title("Bearbeitungszeit je Anfrage")
    if len(series) > 1:
        ax.legend(loc="upper right")
    save(fig, out / "abend-anfragen")


# --- the rush: a premiere selling out --------------------------------------

def rush_stats(run: Run) -> dict:
    m = run.summary
    durations = [ms for _, _, ms, _ in run.requests]
    sold, seats = m["seats_sold"]["value"], m["hall_seats"]["value"]
    confirmed = m["seats_confirmed"]["count"]
    return {
        "requests": len(durations),
        "p50": pct(durations, .5), "p95": pct(durations, .95), "max": max(durations),
        "sold_out_after_s": m["iteration_duration"]["max"] / 1000,
        "sold": sold, "seats": seats, "confirmed": confirmed,
        # a seat promised to two guests would show as more confirmations than sales
        "oversold": max(0, confirmed - sold),
        "unsold": seats - sold,
        "still_held": m["seats_still_held"]["value"],
        "rejected_after_hold": m["bookings_rejected_after_hold"]["count"],
        "holds_lost": m["holds_lost_to_others"]["count"],
        "guests_without_seats": m["guests_without_seats"]["count"],
        "failed_requests": m["http_req_failed"]["passes"],
        "pods_at_start": run.meta["checks"]["pods_at_start"],
    }


def chart_rush_cdf(series: list[tuple[str, list[Run]]], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.3, 2.9))
    for index, (label, runs) in enumerate(series):
        durations = sorted(ms / 1000 for run in runs for _, _, ms, _ in run.requests)
        n = len(durations)
        ax.plot(durations, [100 * (i + 1) / n for i in range(n)], color=COLORS[index], lw=1.6, label=label)
        p95 = pct(durations, .95)
        ax.scatter([p95], [95], s=30, color=COLORS[index], edgecolor="white", linewidth=1.2, zorder=3)
        # alternately right below and left above its dot, so each label sits by its own curve
        right = index % 2 == 0
        ax.annotate(f"p95: {de(p95, 1)} s", (p95, 95), xytext=(7, -13) if right else (-7, 5),
                    textcoords="offset points", ha="left" if right else "right",
                    color=INK_2, fontsize=7.5)
    ax.set_ylim(0, 102)
    ax.set_xlim(left=0)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{de(v)} %"))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: de(v, 1)))
    ax.set_xlabel("Antwortzeit (s)")
    ax.set_title("Ansturm: Anteil der Anfragen, die nach x Sekunden beantwortet waren")
    if len(series) > 1:
        ax.legend(loc="lower right")
    save(fig, out / "ansturm-antwortzeiten")


# --- tables ---------------------------------------------------------------

RAMP_ROWS = [  # (key, label, digits)
    ("peak_rps", "Anfragen/s bei voller Last", 0),
    ("p95", "p95 über den ganzen Test (ms)", 0),
    ("peak_p95", "p95 bei voller Last (ms)", 0),
    ("p99", "p99 über den ganzen Test (ms)", 0),
    ("failed_pct", "Fehlerquote (%)", 3),
    ("peak_pods", "Pods bei voller Last", 0),
    ("max_pods", "Pods höchstens", 0),
    ("scaled_at_rps", "Hochskaliert bei (Anfragen/s)", 0),
    ("cpu_ms_per_visitor", "Backend-CPU je Besucher bei voller Last (ms)", 1),
    ("cpu_ms_per_visitor_run", "Backend-CPU je Besucher, ganzer Test (ms)", 1),
    ("cpu_ms_per_request", "Backend-CPU je Anfrage bei voller Last (ms)", 2),
    ("throttled_pct", "Gedrosselte CPU-Zeitscheiben (%)", 0),
]
RUSH_ROWS = [
    ("p50", "Ansturm: Median (ms)", 0),
    ("p95", "Ansturm: p95 (ms)", 0),
    ("sold_out_after_s", "Ansturm: ausverkauft nach (s)", 1),
    ("holds_lost", "Ansturm: verlorene Reservierungsversuche", 0),
]
# counted over all runs: each one is a guest let down, however rare
RUSH_COUNTS = [
    ("oversold", "Ansturm: Plätze doppelt zugesagt"),
    ("unsold", "Ansturm: Plätze unverkauft"),
    ("still_held", "Ansturm: Plätze am Ende noch reserviert"),
    ("rejected_after_hold", "Ansturm: Buchung trotz Reservierung abgelehnt"),
    ("failed_requests", "Ansturm: fehlgeschlagene Anfragen"),
]


def cell(values: list, digits: int) -> str:
    present = [v for v in values if v is not None]
    if not present:
        return "–"
    mid = de(statistics.median(present), digits)
    low, high = de(min(present), digits), de(max(present), digits)
    return mid if low == high else f"{mid} ({low}–{high})"


def count_cell(values: list) -> str:
    if not values:
        return "–"
    total, hit = sum(values), sum(1 for v in values if v)
    return f"{de(total)} (in {hit} von {len(values)} Läufen)" if total else "0"


def tables(series, ramp, rush, out: Path) -> str:
    labels = [label for label, _ in series]
    rows = []
    for key, text, digits in RAMP_ROWS:
        rows.append([text, *(cell([s[key] for s in ramp[label]], digits) for label in labels)])
    for key, text, digits in RUSH_ROWS:
        rows.append([text, *(cell([s[key] for s in rush[label]], digits) for label in labels)])
    for key, text in RUSH_COUNTS:
        rows.append([text, *(count_cell([s[key] for s in rush[label]]) for label in labels)])
    head = ["", *labels]

    markdown = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    markdown += ["| " + " | ".join(row) + " |" for row in rows]
    note = "Median der Läufe, in Klammern der kleinste und der größte Wert."
    (out / "zusammenfassung.md").write_text("\n".join(markdown) + f"\n\n{note}\n", encoding="utf-8")

    def tex(text: str) -> str:
        return text.replace("%", r"\%").replace("&", r"\&").replace("_", r"\_").replace("–", "--")

    latex = [r"\begin{tabular}{l" + "r" * len(labels) + "}", r"\toprule",
             " & ".join(tex(h) for h in head) + r" \\", r"\midrule"]
    latex += [" & ".join(tex(c) for c in row) + r" \\" for row in rows]
    latex += [r"\bottomrule", r"\end{tabular}"]
    (out / "tabelle.tex").write_text("\n".join(latex) + "\n", encoding="utf-8")

    with open(out / "laeufe.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        keys = sorted({k for stats in (*ramp.values(), *rush.values()) for s in stats for k in s})
        writer.writerow(["series", "scenario", "run", *keys])
        for label, runs in series:
            for run in runs:
                stats = ramp_stats(run) if run.meta["scenario"] == "ramp" else rush_stats(run)
                writer.writerow([label, run.meta["scenario"], run.meta["run"], *(stats.get(k, "") for k in keys)])

    table_html = "<table><thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in head) + "</tr></thead><tbody>"
    table_html += "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>" for row in rows)
    return table_html + f"</tbody></table><p class=note>{note}</p>"


def index_html(series, table: str, charts: list[str], out: Path) -> None:
    runs = []
    for label, items in series:
        for run in items:
            rel = Path("..") / run.folder.relative_to(RESULTS)
            checks = run.meta["checks"]
            link = (f'<a href="{(rel / "report.html").as_posix()}">k6-Bericht</a>'
                    if (run.folder / "report.html").exists() else "kein k6-Bericht (zu kurz)")
            runs.append(
                f"<tr><td>{html.escape(label)}</td><td>{run.meta['run']}</td>"
                f"<td>{run.meta['start'][:16].replace('T', ' ')} UTC</td><td>{link}</td>"
                f"<td>{checks['dropped_iterations']} verworfen · {de(checks['max_cores_elsewhere'], 2)} Kerne fremd"
                f" · Image {html.escape(run.meta['backend_image'].split(':')[-1])}"
                f"{'<br>' + html.escape(run.meta['note']) if run.meta.get('note') else ''}</td></tr>")
    images = "".join(f'<figure><img src="{name}.png" alt="{name}"></figure>' for name in charts)
    page = f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lasttests im Vergleich</title>
<style>
  :root {{ color-scheme: light; --ink: {INK}; --ink-2: {INK_2}; --muted: {MUTED}; --line: {GRID}; }}
  body {{ margin: 0; background: #fcfcfb; color: var(--ink); font: 15px/1.5 system-ui, "Segoe UI", sans-serif; }}
  main {{ max-width: 860px; margin: 0 auto; padding: 32px 16px 64px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }} h2 {{ font-size: 16px; margin: 40px 0 12px; }}
  p.note, .sub {{ color: var(--ink-2); font-size: 13px; }}
  table {{ border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; font-size: 13px; }}
  th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }}
  td + td, th + th {{ text-align: right; }} .runs td, .runs th {{ text-align: left; }}
  figure {{ margin: 0 0 24px; }} img {{ width: 100%; height: auto; }}
  .scroll {{ overflow-x: auto; }} a {{ color: #1c5cab; }}
</style></head><body><main>
<h1>Lasttests im Vergleich</h1>
<p class=sub>{" · ".join(html.escape(label) for label, _ in series)}</p>
<h2>Kennzahlen</h2><div class=scroll>{table}</div>
<h2>Diagramme</h2>{images}
<h2>Läufe</h2><div class=scroll><table class=runs><thead><tr><th>Messreihe</th><th>Lauf</th><th>Beginn</th>
<th>Bericht</th><th>Plausibilität</th></tr></thead><tbody>{"".join(runs)}</tbody></table></div>
</main></body></html>
"""
    (out / "index.html").write_text(page, encoding="utf-8")


def save(fig, path: Path) -> None:
    fig.savefig(path.with_suffix(".pdf"))
    fig.savefig(path.with_suffix(".png"))
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare load test series.")
    parser.add_argument("series", nargs="+", help="series name in results/, optionally name=label")
    parser.add_argument("--out", type=Path, help="default: results/vergleich-<series>")
    args = parser.parse_args()

    series = []
    for item in args.series:
        name, _, label = item.partition("=")
        runs = [Run(d) for d in sorted((RESULTS / name).iterdir()) if (d / "meta.json").exists()]
        series.append((label or name, runs))
    out = args.out or RESULTS / ("vergleich-" + "-".join(item.partition("=")[0] for item in args.series))
    out.mkdir(parents=True, exist_ok=True)

    ramp = {label: [ramp_stats(r) for r in runs if r.meta["scenario"] == "ramp"] for label, runs in series}
    rush = {label: [rush_stats(r) for r in runs if r.meta["scenario"] == "rush"] for label, runs in series}
    ramp_series = [(label, [r for r in runs if r.meta["scenario"] == "ramp"]) for label, runs in series]
    rush_series = [(label, [r for r in runs if r.meta["scenario"] == "rush"]) for label, runs in series]

    charts = []
    if all(runs for _, runs in ramp_series):
        chart_ramp_timeline(ramp_series, out)
        chart_dots(ramp_series, [
            ("Backend-CPU je Besucher bei voller Last", lambda r: ramp_stats(r)["cpu_ms_per_visitor"]),
            ("Backend-CPU je Besucher über den ganzen Test", lambda r: ramp_stats(r)["cpu_ms_per_visitor_run"]),
        ], "ms", "abend-cpu-je-besucher", out)
        chart_endpoints(ramp_series, out)
        charts += ["abend-verlauf", "abend-cpu-je-besucher", "abend-anfragen"]
        for _, runs in ramp_series:
            chart_percentiles(runs, out)
            charts.append(f"abend-perzentile-{runs[0].folder.parent.name}")
    if all(runs for _, runs in rush_series):
        chart_rush_cdf(rush_series, out)
        charts.append("ansturm-antwortzeiten")
    index_html(series, tables(series, ramp, rush, out), charts, out)
    print(f"written to {out}")


if __name__ == "__main__":
    main()
