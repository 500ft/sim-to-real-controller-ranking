#!/usr/bin/env python
"""Render synchronized positions sampled from committed simulator telemetry."""

from __future__ import annotations

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
OUT = ROOT / "runs/controller_pipeline"
STYLES = {"pure_pursuit": ("#0072B2", "o", "PP"),
          "lqr": ("#D55E00", "s", "LQR"), "mpc": ("#009E73", "^", "MPC")}


def render() -> None:
    traces = {name: pd.read_csv(OUT / f"baseline_nominal_{name}.csv.gz") for name in STYLES}
    results = {name: json.loads((OUT / f"baseline_nominal_{name}.json").read_text()) for name in STYLES}
    waypoints = np.loadtxt(ROOT / "examples/example_waypoints.csv", delimiter=";", skiprows=3)
    meta = yaml.safe_load((ROOT / "examples/example_map.yaml").read_text())
    image = np.asarray(Image.open(ROOT / "examples/example_map.png").convert("L").transpose(Image.FLIP_TOP_BOTTOM))
    ox, oy, _ = meta["origin"]
    resolution = meta["resolution"]
    extent = (ox, ox + image.shape[1] * resolution, oy, oy + image.shape[0] * resolution)

    plt.rcParams.update({"font.size": 11, "axes.titlesize": 13})
    fig, ax = plt.subplots(figsize=(9.6, 5.4), dpi=100)
    fig.subplots_adjust(left=0.08, right=0.78, top=0.88, bottom=0.13)
    ax.imshow(image, cmap="gray", origin="lower", extent=extent, vmin=0, vmax=255)
    ax.plot(waypoints[:, 1], waypoints[:, 2], color="0.45", lw=0.9, ls="--", label="source line")
    artists = {}
    trails = {}
    for name, (color, marker, label) in STYLES.items():
        trails[name], = ax.plot([], [], color=color, lw=1.4, alpha=0.8)
        artists[name], = ax.plot([], [], marker=marker, markersize=8, markerfacecolor=color,
                                 markeredgecolor="white", linestyle="none", label=label)
    xy = waypoints[:, 1:3]
    ax.set_xlim(float(xy[:, 0].min() - 3), float(xy[:, 0].max() + 3))
    ax.set_ylim(float(xy[:, 1].min() - 3), float(xy[:, 1].max() + 3))
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("Example-track controller replay | simulation")
    ax.grid(color="0.7", alpha=0.2, lw=0.5)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False)
    time_text = fig.text(0.79, 0.66, "", fontsize=12)
    statuses = {name: fig.text(0.79, 0.59 - i * 0.07, "", color=STYLES[name][0], fontsize=10)
                for i, name in enumerate(STYLES)}
    fig.text(0.79, 0.18, "Positions are sampled\nfrom 2 ms telemetry.\nNo pose interpolation.", fontsize=9)
    duration = max(float(trace["time_s"].iloc[-1]) for trace in traces.values())
    fps = 12
    writer = FFMpegWriter(fps=fps, codec="libx264", bitrate=1200,
                          extra_args=["-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    destination = OUT / "example_controller_overlay.mp4"
    with writer.saving(fig, str(destination), dpi=100):
        for frame_idx in range(int(np.ceil(duration * fps)) + 1):
            t = min(frame_idx / fps, duration)
            time_text.set_text(f"Time: {t:5.2f} s")
            for name, trace in traces.items():
                times = trace["time_s"].to_numpy(float)
                idx = max(0, min(len(times) - 1, int(np.searchsorted(times, t, side="right") - 1)))
                artists[name].set_data([trace["x_m"].iloc[idx]], [trace["y_m"].iloc[idx]])
                trails[name].set_data(trace["x_m"].iloc[:idx + 1:25], trace["y_m"].iloc[:idx + 1:25])
                label = STYLES[name][2]
                if t < times[-1]:
                    status = "running"
                else:
                    status = {"completed_lap": "Gym finish", "collision": "collision",
                              "max_steps": "time limit"}.get(results[name]["termination_reason"], "stopped")
                statuses[name].set_text(f"{label}: {status}")
            writer.grab_frame()
    plt.close(fig)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(duration / 2), "-i", str(destination),
                    "-frames:v", "1", str(OUT / "example_controller_preview.png")], check=True)
    print(destination)


if __name__ == "__main__":
    render()
