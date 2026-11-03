# MATLAB figure scripts

MATLAB R2025b draws the report figures and the headline result tables from the
committed run files. No toolbox is needed. Python still owns the plotted values,
the captions and the checks; these scripts only draw.

## Regenerate

Run from the repository root. Refresh the captions and the derived tables in
`reports/figures/data/` first, then draw:

```bash
PYTHONPATH=gym MPLBACKEND=Agg python experiments/report_figures.py
matlab -batch "addpath('experiments/matlab'); render_figures"
```

`render_figures` writes `<name>.pdf` (vector) and `<name>.png` (300 dpi) to
`reports/figures/` and `evidence/item11/figures/`, and the table fragments to
`reports/figures/tables/`. Redraw one family with, for example,
`matlab -batch "addpath('experiments/matlab'); render_figures([], [], {'ekf'})"`.
A failing family prints its error and the rest still run.

Typeset each table fragment in a standalone LaTeX document that loads
`booktabs`, `siunitx` (with `group-separator={,}`) and `fontspec`, then
rasterise the PDF at 300 dpi with `pdftoppm -r 300 -png -singlefile`. The
owner's figure kit wraps both steps:

```bash
python table2img.py reports/figures/tables/ekf_summary.tex reports/figures/tables/ekf_summary
```

## Files

| Script | Figures or tables |
| --- | --- |
| `make_integrator.m` | `first_integrator_comparison`, `integrator_trajectory_overlay`, `integrator_tracking_error_vs_progress`, `integrator_summary_metrics` |
| `make_convergence.m` | `integrator_convergence_position_error`, `integrator_convergence_metrics` |
| `make_dynamic_replay.m` | `dynamic_replay_yaw_rate_overlay`, `dynamic_replay_state_errors` |
| `make_kinematic_replay.m` | `model_vs_gym_trajectory_error`, `model_vs_gym_state_errors` |
| `make_excitation.m` | `sysid_steering_input`, `sysid_yaw_response`, `sysid_speed_hold` |
| `make_parameter_fit.m` | `dynamic_parameter_fit`, `dynamic_parameter_residuals` |
| `make_pure_pursuit.m` | `pure_pursuit_sweep_rms_cte_heatmap`, `pure_pursuit_sweep_lap_time_heatmap`, `pure_pursuit_sweep_regions` |
| `make_ekf.m` | `ekf_position_error_over_time`, `ekf_rmse_summary`, `ekf_dropout_zoom` |
| `make_fmea.m` | `fmea_rpn_bar`, `fmea_detection_signals` |
| `make_parameter_id.m` | `parameter_id_noise_degradation`, `parameter_id_latency_degradation`, `parameter_id_condition_number` |
| `make_item11.m` | `evidence/item11/figures/`: `steering_command_vs_achieved`, `enriched_ros_fit`, `enriched_ros_residuals` |
| `make_ope_structure.m` | `ope_structure` |
| `make_command_response.m` | `real_command_response` |
| `make_tables.m` | `reports/figures/tables/`: `controller_comparison`, `dynamic_replay_yaw_rate`, `ekf_summary`, `parameter_id_robustness`, `command_response`, `ope_structure` |

`fig_style.m` sets the shared rules: LaTeX text, 9/8/7 pt sizes and MATLAB's
default blue and orange. `export_pair.m` writes the PDF and PNG. Helpers that
several scripts share are in `private/`.
