# Your Energy Mate

A small web app that tells a household whether its electricity use is risky *right now*, and what to switch off.

Built for EE3055 Soft Computing. It combines two soft-computing techniques:

- **ANN (TensorFlow/Keras)** predicts how much electricity a household *normally* uses in the current hour.
- **Mamdani fuzzy system (MATLAB)** turns "how far above normal" plus the current tariff into a 0 – 100 risk score.

The page then turns the score into plain advice such as *"Consumption is already high. Turn off the Air Conditioner now."*

## How it works

```
Browser (frontend/)
   │  POST /api/risk  { household_id, actual_kwh }
   ▼
backend/server.py
   ├─ models/ann/live_predict.py
   │     ANN expected kWh for :00 and :30 of the current hour → summed
   │     consumption % = actual / expected × 100 (capped at 300)
   │     tariff code from the hour (India time)
   └─ models/fuzzy/evaluateEnergyRisk.m   (via MATLAB Engine)
         [consumption %, tariff] → risk score 0–100
   ▼
{ consumption_pct, tariff, tariff_name, risk_score }
```

The UI sends two requests per change: one for the base load and one for base + the appliances switched on, so you can see how much the appliances add.

### Tariff (India time)

| Hours       | Code | Tariff   |
|-------------|------|----------|
| 06:00–18:00 | 1    | Normal   |
| 18:00–22:00 | 2    | Peak     |
| otherwise   | 0    | Off-peak |

### Fuzzy system

Inputs: `ConsumptionPct` (0–300: Low, Normal, High, VeryHigh) and `Tariff` (0–2: OffPeak, Normal, Peak).
Output: `RiskScore` (0–100: Low, Moderate, High, VeryHigh). Min/max inference, centroid defuzzification, 12 rules.

| Consumption ↓ / Tariff → | Off-peak | Normal   | Peak     |
|--------------------------|----------|----------|----------|
| Low                      | Low      | Low      | Moderate |
| Normal                   | Low      | Moderate | High     |
| High                     | Moderate | High     | VeryHigh |
| VeryHigh                 | High     | VeryHigh | VeryHigh |

The UI reads the score as Low (< 27), Moderate (27–55), High (55–80), Very high (≥ 80).

## Requirements

- Python 3.10+ (developed on 3.13)
- MATLAB with the **Fuzzy Logic Toolbox** and the **MATLAB Engine API for Python** (its version must match your MATLAB release and support your Python version)
- Training data: half-hourly smart-meter CSVs with columns `LCLid`, `DateTime`, `KWH/hh (per half hour)` (the London smart meter dataset)

## Setup

```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install matlabengine==<version for your MATLAB>   # see requirements.txt
```

## Train the ANN

Put the raw CSVs in `data/raw/`, then from the project root:

```bash
python models/ann/train.py --data-dir data/raw/
```

Useful options: `--max-households 0` (default; `0` = all, needs a lot of RAM), `--epochs 30`, `--no-cache`.
This writes `models/ann/saved_model/energy_ann.keras` and `models/ann/preprocessing/preprocessing.json`.

A trained model is included in the repo, so you can skip this step to just run the app.

## Rebuild the fuzzy system (only if you change it)

In MATLAB, from `models/fuzzy/`:

```matlab
>> build_EnergyRisk
```

This regenerates `EnergyRisk.fis` and runs a few test cases.

## Run

```bash
python backend/server.py
```

Open http://127.0.0.1:8000. The first request is slow because MATLAB and TensorFlow start up.

### API

`POST /api/risk`

```json
{ "household_id": "MAC000002", "actual_kwh": 0.8 }
```

Optional: `"datetime": "2026-11-10T19:00:00+05:30"` to evaluate a specific time instead of now.

```json
{
  "household_id": "MAC000002",
  "actual_kwh": 0.8,
  "consumption_pct": 106.25,
  "tariff": 2,
  "tariff_name": "Peak",
  "risk_score": 70.0
}
```

Errors come back as `{ "error": "..." }`.

## Project structure

```
backend/server.py            HTTP server: static frontend + /api/risk
frontend/                    index.html + js/app.js (plain HTML/JS, no build step)
models/ann/                  preprocess, train, predict, live_predict + saved model
models/fuzzy/                build_EnergyRisk.m, evaluateEnergyRisk.m, EnergyRisk.fis
data/raw, data/processed     datasets (not committed)
```

## Limitations

- The dataset is from London, so predictions for other places or dates are extrapolations from London seasonal and daily patterns.
- The "appliances" in the UI are simple fixed estimates (AC 1 kWh, washing machine 0.375 kWh, iron 0.25 kWh).
