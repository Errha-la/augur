# Swapping the lap-time model

> **Status:** sections 2–4 and steps 1–4 of section 3 were run against the code on 2026-11-19 (`prediction-and-events` task 6.1). Step 5's settings panel, step 6 (`augur.bench`), and the matching errors in section 5 come from later changes (`race-dashboard`, `race-wrapped`, `polish`) and are not implemented yet; task 5.1 of `race-wrapped` checks them.

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
        self.mean_ = float(target.mean())  # replace with your training on features -> delta

    def predict(self, features: pd.DataFrame) -> pd.Series:
        return pd.Series(self.mean_, index=features.index)  # one delta (seconds) per row

    def save(self, path: str) -> None:
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str) -> "MyModel":
        return joblib.load(path)
```

**2. Register it.** Add these lines at the end of `backend/src/augur/models/registry.py`, after `register(LightGBMModel)`:

```python
from augur.models.mymodel import MyModel  # noqa: E402

register(MyModel)
```

The name must match `^[a-z][a-z0-9_]*$` (it becomes a file name) and the class needs `name`, `author`, `fit`, `predict`, `save`, and `load`.

**3. Train it.** Do not train on the benchmark races (2024 Bahrain and 2024 Abu Dhabi).

```bash
python -m augur.train --model mymodel --train 2024:2-11
```

This writes `data/models/mymodel.joblib` and `data/models/mymodel_metrics.json`, and prints both MAE values:

```
mymodel: mae_model_s=0.3881 mae_baseline_s=0.3802 (n_train=8161, n_test=1773)
```

(That output is from the example class above, which predicts the mean training delta.) `--train` and `--test` take `<year>:<rounds>`, such as `2024:2-11` or `2024:1,24`; the defaults are `2024:2-11` and `2024:1,24`. Training races must not overlap the test races.

**4. Analyze each race** you want to replay with it:

```bash
python -m augur.analyze --race 2024-01-bahrain-grand-prix --model mymodel
python -m augur.analyze --race 2024-24-abu-dhabi-grand-prix --model mymodel
```

Each prints `analyzed <race_id>: <n> events`. The command refuses a race listed in the model's `train_races`.

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
| `model mymodel is not trained, run augur.train first` (`augur.analyze`, or HTTP 503 from the API) | `data/models/mymodel.joblib` is missing | Step 3 |
| `race <race_id> is in the training set of model mymodel` | `augur.analyze` on a training race | Analyze a test race instead |
| `train and test races overlap: <race_id>` | The same race is in `--train` and `--test` | Remove it from one list |
| "Race not analyzed" in the dashboard | No events for this race and model | Step 4 |
| `benchmark race ... is in the training set` | The training races include 2024 Bahrain or Abu Dhabi | Retrain without them |
| `missing race 2024-05, run augur.ingest first` | A training or test race is not downloaded (shown as `<year>-<round>` until ingested) | `python -m augur.ingest --year <year> --rounds <rounds>` |

## 6. Not supported yet

These ideas were discussed and deferred:

- Replacing the finishing-position simulator directly, for example with your own classifier, through a model bundle that can override the lap-time model, the position predictor, or both.
- Dropping a `.py` file into a `models/` folder instead of registering it in code.
- Running `augur.analyze` from the settings panel with an "Analyze now" button.
