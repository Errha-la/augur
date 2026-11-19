"""Circuit degradation priors from the previous season's race at the same location."""

from __future__ import annotations

from augur.models.degradation import compound_median_slopes
from augur.replay import ReplayStore


def circuit_priors(store: ReplayStore, race_id: str) -> dict[str, float]:
    """compound -> median stint slope of the prior race; empty when none is ingested.

    The prior race is fully in the past, so reading all of its laps is not a
    leak for the current race.
    """
    prior_id = store.find_prior_race(race_id)
    if prior_id is None:
        return {}
    prior = store.get_race(prior_id)
    total = int(prior["total_laps"])
    return compound_median_slopes(store.laps_until(prior_id, total), total)
