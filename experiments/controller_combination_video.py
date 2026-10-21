"""Render synchronized combination traces with applied actions and switch status."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
import numpy as np
import pandas as pd
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/controller_combinations"
GROUPS = (
    (("pp", "PP", "#2C49A6", "o"), ("pp_lqr", "PP+LQR", "#2F7D5B", "s"),
     ("pp_mpc", "PP+MPC", "#B0492F", "^")),
    (("lqr_active_mpc_shadow", "LQR active, MPC shadow", "#2F7D5B", "s"),
     ("mpc_active_lqr_shadow", "MPC active, LQR shadow", "#B0492F", "^")),
    (("mpc_lqr_fallback", "MPC→LQR fallback", "#B0492F", "D"),
     ("pp_blend", "PP+blend", "#2C49A6", "P")),
)


def render(track: str, scenario: str, timing: str) -> tuple[Path, Path]:
    if track == "example":
        image_path, yaml_path = ROOT / "examples/example_map.png", ROOT / "examples/example_map.yaml"
    else:
        image_path = ROOT / "third_party/mapzoo_berlin/berlin.png"
        yaml_path = ROOT / "third_party/mapzoo_berlin/berlin.yaml"
    protocol = json.loads((OUT / "protocol.json").read_text())
    line = np.loadtxt(ROOT / protocol["tracks"][track]["line"], delimiter=";", skiprows=3)
    names = [item[0] for group in GROUPS for item in group]
    traces = {name: pd.read_csv(OUT / f"{track}_{scenario}_{timing}_{name}.csv.gz") for name in names}
    results = {name: json.loads((OUT / f"{track}_{scenario}_{timing}_{name}.json").read_text()) for name in names}
    meta = yaml.safe_load(yaml_path.read_text())
    raster = np.asarray(Image.open(image_path).convert("L").transpose(Image.FLIP_TOP_BOTTOM))
    ox, oy, _ = meta["origin"]
    resolution = meta["resolution"]
    extent = (ox, ox + raster.shape[1] * resolution, oy, oy + raster.shape[0] * resolution)
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 11})
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.0), dpi=100)
    fig.subplots_adjust(left=.07, right=.98, bottom=.08, top=.90, wspace=.18, hspace=.36)
    x, y = line[:, 1], line[:, 2]
    artists = {}
    trails = {}
    labels = {}
    for ax, group, title in zip(axes.flat[:3], GROUPS,
                                ("Frozen baselines", "Diagnostic shadows", "Fallback and blend")):
        ax.imshow(raster, cmap="gray", origin="lower", extent=extent, vmin=0, vmax=255)
        ax.plot(x, y, color=".55", ls="--", lw=.8)
        for name, label, color, marker in group:
            trails[name], = ax.plot([], [], color=color, lw=1.0, alpha=.75)
            artists[name], = ax.plot([], [], color=color, marker=marker, ms=6,
                                     mec="white", ls="none", label=label)
        ax.set_xlim(float(x.min() - 2), float(x.max() + 2))
        ax.set_ylim(float(y.min() - 2), float(y.max() + 2))
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.set_title(title)
        ax.grid(color=".8", alpha=.25, lw=.5)
        ax.legend(loc="upper center", bbox_to_anchor=(.5, -.14), ncol=len(group), frameon=False, fontsize=8)
        labels[title] = ax.text(.01, .01, "", transform=ax.transAxes, ha="left", va="bottom",
                                fontsize=8, bbox={"facecolor": "white", "alpha": .85, "edgecolor": "none"})
    ax_command = axes.flat[3]
    for name, _, color, marker in GROUPS[2]:
        frame = traces[name]
        ax_command.plot(frame["time_s"], frame["command_steer_rad"], color=color, lw=1.1, label=name)
    cursor = ax_command.axvline(0, color="#BE933A", ls="--", lw=1)
    ax_command.set_xlabel("Simulation time [s]")
    ax_command.set_ylabel("Applied steering [rad]")
    ax_command.set_title("Applied command, fallback and blend")
    ax_command.grid(axis="y", color=".8", alpha=.3)
    ax_command.legend(frameon=False, fontsize=8)
    duration = max(float(frame["time_s"].iloc[-1]) for frame in traces.values())
    fig.suptitle(f"{track} · {scenario} · {timing} · simulation development\n"
                 "Same map, line, start, seed and model per architecture; Gym finish may require two circuits", fontsize=12)
    destination = OUT / f"{track}_{scenario}_{timing}_comparison.mp4"
    preview = OUT / f"{track}_{scenario}_{timing}_preview.png"
    writer = FFMpegWriter(fps=10, codec="libx264", bitrate=1400,
                          extra_args=["-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    with writer.saving(fig, str(destination), dpi=100):
        for frame_index in range(int(np.ceil(duration * 10)) + 1):
            at = min(frame_index / 10.0, duration)
            cursor.set_xdata([at, at])
            for group, title in zip(GROUPS, ("Frozen baselines", "Diagnostic shadows", "Fallback and blend")):
                status = []
                for name, label, _, _ in group:
                    trace = traces[name]
                    times = trace["time_s"].to_numpy(float)
                    index = max(0, min(len(times) - 1, int(np.searchsorted(times, at, side="right") - 1)))
                    artists[name].set_data([trace["x_m"].iloc[index]], [trace["y_m"].iloc[index]])
                    trails[name].set_data(trace["x_m"].iloc[:index + 1:25], trace["y_m"].iloc[:index + 1:25])
                    state = ("running" if at < times[-1] else results[name]["termination_reason"])
                    active = trace["applied_active_component"].iloc[index]
                    shadow = trace["applied_shadow_component"].iloc[index]
                    if pd.isna(shadow):
                        shadow = "none"
                    event_rows = trace.iloc[:index + 1].drop_duplicates("applied_call_index")
                    switch_count = int(event_rows["applied_switch_reason"].isin(
                        ["mpc_failure_or_deadline", "mpc_recovered"]).sum())
                    status.append(f"{label}: {state}; active {active}; shadow {shadow}; "
                                  f"switches {switch_count}; applied {trace['command_steer_rad'].iloc[index]:+.2f} rad")
                labels[title].set_text("\n".join(status))
            writer.grab_frame()
    plt.close(fig)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(duration / 2),
                    "-i", str(destination), "-frames:v", "1", str(preview)], check=True)
    return destination, preview


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("track", choices=["example", "mapzoo_berlin"])
    parser.add_argument("scenario", choices=["nominal", "mpc_timeout"])
    parser.add_argument("timing", choices=["ideal", "deadline_aware"])
    args = parser.parse_args()
    print(*render(args.track, args.scenario, args.timing))
