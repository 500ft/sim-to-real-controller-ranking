# Bridge runtime and determinism benchmark

The registered bridge executed 60 runs and 3,263 control steps from one
recorded real start pose: three modes, seeds 0 to 9, two repeats each. The
[result](../runs/bridge_runtime_benchmark/result.json) owns every number; the
[protocol](../runs/bridge_runtime_benchmark/protocol.json) fixed the modes,
seeds, start rule, checks and checkpoint method before the run. No reward from
these runs enters a ranking.

Same-seed repeats are bitwise identical whenever the seed is not asked to do
anything. In `fixed` mode (recorded pose, 0.5 m/s, zero normalized action) all
20 runs produce one trajectory and collide after 47 steps. In `seeded_actions`
mode, where the actions come from `numpy.random.default_rng(seed)`, the two
repeats of every seed agree in every recorded state, action and reward, and the
ten seeds give ten trajectories that end in collision between 38 and 161
steps. In `env_velocity` mode, where no start velocity is supplied and the
candidate's `RandomResetVelocity` draws one, no same-seed pair agrees: the
drawn velocities differ between repeats, every reset advances the global numpy
generator, and no reset reseeds it. The seed-propagation defect named in the
[reward bridge report](ope_reward_adapter_qualification.md) is therefore present
and now has executed evidence: `env.reset(seed)` reaches neither the velocity
draw nor the base environment, because `AccelerationAndDeltaSteeringWrapper`
and `PoseStartPosition` call the inner reset without the seed, and
`F110Env.reset` would in any case reseed with its config seed 12345. Extended
rollouts that rely on `reset(seed)` for simulator randomness would not be
reproducible from the seed alone; supplying every stochastic input explicitly,
as the registered modes do, restores bitwise repeatability.

Checkpoint and restart work through `pickle`. The bridge environment and the
action generator serialize to 250 KB in 2 to 7 ms and restore in 1 to 25 ms.
The restored copy reproduces the uninterrupted run bitwise for all 81 steps
after the amended checkpoint on the seed 9 run, and for the single step that
remained after the originally registered checkpoint on the seed 0 run, which
collided at step 126. The protocol records that the second check was added
after the first execution, chosen on step count only.

Runtime on this host (Darwin arm64, Python 3.11.15, numpy 1.26.4) ranged from
96 to 814 control steps per second across the 60 runs, with per-mode medians
of 199, 620 and 758. The mean step time within a run is flat across step-index
bins (1.15 to 1.32 ms in `seeded_actions`), so the slow runs reflect host load
during the run rather than growth with episode length; three executions of the
same protocol on this host gave per-mode medians between 199 and 791. At the
observed rates, 15 agents, 10 seeds and 250 steps would need roughly one to
seven minutes of simulator time per reward definition before policy cost.
Environment construction took 2.0 to 5.5 s. Peak resident memory
(`ru_maxrss`) was 194.5 MB after the first construction and 227.8 MB at the
end. Host timing is development evidence only.

No run reached 250 steps. Driving straight from the registered start pose hits
a wall after 47 control steps, and random actions do no better. A 250-step
development rollout therefore needs an executable steering policy; this
benchmark characterizes the bridge, not any controller. The registered start
pose and velocity stay in the private step ledger; the public result records
the start row and the SHA-256 of the pose and velocity list.

## Reproduce

Use Python 3.11 with `requirements-ope-corrected-v2.txt`, the pinned loader
and gym importable, the candidate simulator root on `PYTHONPATH`, and the
corrected real ZIP and root outside git:

```bash
python -m unittest experiments.test_benchmark_bridge_runtime_v2
PYTHONPATH=/private/pinned-simulator python -m experiments.benchmark_bridge_runtime_v2 \
  --simulator-source /private/pinned-simulator --loader-source /private/pinned-loader \
  --real-zip /private/data/f110-real-stoch-v2.zip --real-root /private/data/f110-real-stoch-v2 \
  --private-steps /private/bridge-benchmark-steps.jsonl --out /tmp/result.json
```

`--loader-source` must be the checkout that Python imports, because the bridge
refuses a loader loaded from another path. Trajectory hashes and determinism
verdicts should reproduce exactly; step rates and memory depend on the host.
