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
DEG_WARNING_MIN_LAPS = 5
UNDERCUT_GAP_S = 2.5
UNDERCUT_MIN_TYRE_AGE = 12
UNDERCUT_NO_PIT_LAPS = 3
POSITION_CHANGE_MIN_PLACES = 2

# Model served by the API when AUGUR_MODEL is unset.
DEFAULT_MODEL = "lightgbm"
MODEL_ENV = "AUGUR_MODEL"
