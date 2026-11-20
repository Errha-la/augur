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
# Dirty air: the PITWALL project's documented prior, 0.40 s/lap within 1.0 s.
DIRTY_AIR_GAP_S = 1.0
DIRTY_AIR_PENALTY_S = 0.4

# Model served by the API when AUGUR_MODEL is unset.
DEFAULT_MODEL = "lightgbm"
MODEL_ENV = "AUGUR_MODEL"
