# Swapping the lap-time model

> **Status:** written before implementation, from the Spectra changes `prediction-and-events`, `position-prediction`, `race-wrapped`, and `polish`. Task 6.1 of `prediction-and-events` and task 5.1 of `race-wrapped` check every command here against the real code and update this file.

AUGUR lets you plug in your own **lap-time model**, then compare it with the built-in models on the same benchmark. This page explains what your model changes, how to add it, and what you cannot swap yet.

## 1. What your model changes

You replace one component: the model that predicts each driver's next lap time. Several outputs depend on it.

```
your LapTimeModel
   │
   ├─► next-lap predictions          (/predictions, timing list, focus panel)
   │      ├─► pace_drop events        (fires when a lap is > 1.0 s slower than predicted)
   │      └─► base pace of the full-field simulation
   │              └─► finishing-position probabilities (/positions)
   │                      └─► headline benchmark score (podium skill)
   │
   └─► lap-time MAE                   (second benchmark score)
```

These parts **do not change** when you swap the model:

| Component | Why it stays fixed |
|---|---|
| Tyre degradation fit and cliff check | Explains the race; it is not a score |
| Strategy Monte Carlo | Uses degradation and pit loss, not your model |
| `degradation_warning`, `undercut_window`, `position_change` rules | Rule-based; they do not use lap-time predictions |
| Gemini commentary | Rewrites existing analysis; it predicts nothing |

Results are stored **per model name**: events and position predictions for `mymodel` never mix with those of `lightgbm`.

## 2. What your model receives

The model predicts a **delta**: next clean lap time minus the driver's recent pace (the median of their last 3 clean laps). AUGUR adds the delta back: `prediction = recent_pace_s + delta`.

| Feature | Meaning |
|---|---|
| `tyre_life` | Laps on the current tyres |
| `stint` | Stint number (1 = first stint) |
| `compound` | SOFT, MEDIUM, or HARD |
| `lap_fraction` | Current lap / total laps |
| `laps_since_pit` | Laps since the last pit stop |
| `recent_pace_trend_s` | Last clean lap minus recent pace |
| `circuit_deg_prior_s` | Degradation at this circuit in the previous season (may be null) |
| `team_pace_gap_s` | Team pace minus field pace over the last 5 laps |

Features for lap k are built only from laps before k. Your model receives no driver identity and no future data.

## 3. Steps

**1. Write the class.** Create `backend/src/augur/models/mymodel.py`:

```python
import joblib
import pandas as pd

class MyModel:
    name = "mymodel"
    author = "your-name"

    def fit(self, features: pd.DataFrame, target: pd.Series) -> None:
        ...  # train on features -> delta

    def predict(self, features: pd.DataFrame) -> pd.Series:
        ...  # return one delta (seconds) per row

    def save(self, path: str) -> None:
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str) -> "MyModel":
        return joblib.load(path)
```

**2. Register it** in `augur.models.registry`, next to `lightgbm` and `baseline`.

**3. Train it.** Do not train on the benchmark races (2024 Bahrain and 2024 Abu Dhabi).

```bash
python -m augur.train --model mymodel --train 2023:1-10
```

This writes `data/models/mymodel.joblib` and `data/models/mymodel_metrics.json`.

**4. Analyze each race** you want to replay with it:

```bash
python -m augur.analyze --race 2024-01-bahrain-grand-prix --model mymodel
python -m augur.analyze --race 2024-24-abu-dhabi-grand-prix --model mymodel
```

**5. Serve it.** Choose `mymodel` in the dashboard settings panel (gear button, Stage 3), or start the API with:

```bash
AUGUR_MODEL=mymodel uvicorn augur.api:app --app-dir backend/src
```

If both are set, the settings panel choice wins.

**6. Benchmark it:**

```bash
python -m augur.bench --model mymodel
# mymodel: podium skill 40.0% vs current order, lap times beat baseline by 18.0%, event hit rate 64% (9/14)
```

The result goes to `bench/mymodel.json`. Your model's name and author appear on every Wrapped card.

## 4. Rules

- Keep training and prediction deterministic (fix your random seeds). Otherwise two bench runs give different numbers.
- Read data only through the features you are given. Do not open files under `data/` from inside the model.
- Never train on a benchmark race. `augur.bench` refuses such a model.

## 5. Common errors

| Message | Cause | Fix |
|---|---|---|
| `unknown model mymodel` | The class is not registered | Step 2 |
| `model mymodel is not trained` (settings panel) | `data/models/mymodel.joblib` is missing | Step 3 |
| "Race not analyzed" in the dashboard | No events for this race and model | Step 4 |
| `benchmark race ... is in the training set` | The training races include 2024 Bahrain or Abu Dhabi | Retrain without them |
| `missing race ..., run augur.ingest first` | A training or benchmark race is not downloaded | `python -m augur.ingest --year <year> --rounds <rounds>` |

## 6. Not supported yet

These ideas were discussed and deferred:

- Replacing the finishing-position simulator directly, for example with your own classifier, through a model bundle that can override the lap-time model, the position predictor, or both.
- Dropping a `.py` file into a `models/` folder instead of registering it in code.
- Running `augur.analyze` from the settings panel with an "Analyze now" button.
