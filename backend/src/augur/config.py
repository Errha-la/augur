"""Named thresholds for features, degradation, strategy, and events.

Every value here is an MVP estimate (see the prediction-and-events design,
"Risks / Trade-offs"); they are kept in one place so they can be tuned after
counting events per type on the demo races.
"""

from __future__ import annotations

# Dry compounds; intermediate, wet, and unknown laps are never clean.
DRY_COMPOUNDS: tuple[str, ...] = ("SOFT", "MEDIUM", "HARD")

# Clean-lap filter: at most this many percent slower than the fastest earlier clean lap.
OUTLIER_PCT = 10.0

# Fuel correction: 0.03 s per kg over a 110 kg load burned evenly over the race.
FUEL_S_PER_KG = 0.03
FUEL_LOAD_KG = 110.0

# Recent pace = median of this many most recent clean laps.
RECENT_PACE_LAPS = 3
# Team pace gap window: the laps k-5 .. k-1.
TEAM_PACE_WINDOW = 5

# Stint degradation fit.
MIN_STINT_LAPS = 4
CLIFF_MIN_LAPS = 6
CLIFF_RESIDUAL_S = 0.8

# Strategy simulation.
PIT_OFFSETS: tuple[int, ...] = (1, 3, 5, 8)
PIT_LOSS_FALLBACK_S = 22.0
# Illustrative values seen in public hobby projects, unverified.
DEG_FALLBACK_S_PER_LAP: dict[str, float] = {"SOFT": 0.085, "MEDIUM": 0.050, "HARD": 0.028}
NOISE_MIN_S = 0.2
# Pace of a compound relative to MEDIUM, s/lap (estimates; checked against fuel-corrected
# stint intercepts on the evaluation races, see position-sim-calibration tasks.md).
COMPOUND_PACE_OFFSET_S: dict[str, float] = {"SOFT": -0.6, "MEDIUM": 0.0, "HARD": 0.4}
STRATEGY_RUNS_DEFAULT = 1000
STRATEGY_RUNS_MIN = 100
STRATEGY_RUNS_MAX = 5000
STRATEGY_SEED_DEFAULT = 42

# Event detectors.
PACE_DROP_S = 1.0
PACE_DROP_COOLDOWN_LAPS = 3
DEG_WARNING_S_PER_LAP = 0.10
# Raised from 5 after measuring the demo races: most warnings fired at exactly
# 5 clean laps, where a 5-point line fit is noisy (design: "Event thresholds tuned").
DEG_WARNING_MIN_LAPS = 8
UNDERCUT_GAP_S = 2.5
UNDERCUT_MIN_TYRE_AGE = 12
UNDERCUT_NO_PIT_LAPS = 3
POSITION_CHANGE_MIN_PLACES = 2
# Overcut: the car directly ahead pits on lap N, the driver was less than this many
# seconds behind it after lap N-1, and the driver's tyres lose less than this per lap.
OVERCUT_GAP_S = 3.0
OVERCUT_MAX_DEG_S_PER_LAP = 0.05
OVERCUT_SEVERITY = 55.0

# Event outcomes: laps after an undercut or degradation call that decide it (estimate;
# check hit/miss/void counts on the demo races).
OUTCOME_WINDOW_LAPS = 8

# Position prediction (full-field race simulation).
POSITION_RUNS_DEFAULT = 1000
POSITION_RUNS_MIN = 100
POSITION_RUNS_MAX = 5000
POSITION_SEED_DEFAULT = 42
# Typical dry stint length in laps; estimates, compare with observed stints on the demo races.
STINT_LIFE_LAPS: dict[str, int] = {"SOFT": 20, "MEDIUM": 28, "HARD": 38}
STINT_LIFE_FALLBACK_LAPS = 28
PIT_JITTER_LAPS = 3
# A driver's own stint slope is projected to the flag only from at least this many
# clean laps; shorter or negative fits use the race's compound median instead.
# Measured on Bahrain lap 15: a 5-lap fit of -0.164 s/lap made a backmarker the
# favourite (p_win 0.81) after 42 projected laps.
POSITION_DEG_MIN_FIT_LAPS = 8
# Guarded compound slope for the simulators (position-sim-calibration): the median of
# stint fits with at least POSITION_DEG_MIN_FIT_LAPS clean laps, shrunk toward the circuit
# prior (else DEG_FALLBACK_S_PER_LAP) with this many pseudo-stints, clamped to
# [0, DEG_CAP_S_PER_LAP]. Estimates; the cap sits above the SOFT default with margin.
DEG_SHRINK_STINTS = 3
DEG_CAP_S_PER_LAP = 0.20
# The lap-time model's next-lap delta (prediction minus recent pace) is multiplied by this
# per simulated lap, so a one-lap forecast does not become a race-long pace gap
# (estimate, tuned on the evaluation races by augur.tune_sim).
MODEL_DELTA_DECAY = 0.5
# Standard deviation of the per-run, per-driver pace offset, s/lap, added to every
# simulated lap of a run (estimate, tuned on the evaluation races by augur.tune_sim).
PACE_OFFSET_SD_S = 0.15
# Dirty air: the PITWALL project's documented prior, 0.40 s/lap within 1.0 s.
DIRTY_AIR_GAP_S = 1.0
DIRTY_AIR_PENALTY_S = 0.4

# Model served by the API when AUGUR_MODEL is unset.
DEFAULT_MODEL = "lightgbm"
MODEL_ENV = "AUGUR_MODEL"
