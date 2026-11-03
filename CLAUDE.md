# CLAUDE.md

Your Energy Mate: ANN (expected hourly kWh) + MATLAB Mamdani fuzzy system (risk score) behind a small Python server and a plain HTML/JS page. See README.md for the full overview.

## Commands

Run everything from the project root, with the venv active.

```bash
pip install -r requirements.txt                       # plus matlabengine, see requirements.txt
python models/ann/train.py --data-dir data/raw/       # train the ANN
python backend/server.py                              # serve http://127.0.0.1:8000
python -m models.ann.predict --household MAC000002 --datetime "2026-11-10 12:30:00"
python -m models.ann.live_predict                     # interactive check of consumption % and tariff
```

`predict.py` and `live_predict.py` use relative imports, so run them with `python -m ...` from the root, not as plain scripts. `train.py` is run as a script and imports `preprocess` directly.

Fuzzy system: edit and run `models/fuzzy/build_EnergyRisk.m` in MATLAB to regenerate `EnergyRisk.fis`. There is no test suite yet.

## Layout

- `backend/server.py` : `ThreadingHTTPServer` serving `frontend/` and `POST /api/risk`. Starts one shared MATLAB engine.
- `models/ann/` : `preprocess.py` (cleaning and features), `train.py`, `predict.py` (one 30-minute interval), `live_predict.py` (hourly consumption % and tariff code).
- `models/fuzzy/` : `build_EnergyRisk.m` builds the FIS, `evaluateEnergyRisk.m` evaluates it, `EnergyRisk.fis` is the generated file.
- `frontend/index.html`, `frontend/js/app.js` : vanilla HTML/CSS/JS, no framework, no build step.

## Things that must stay in sync

- **Tariff hours** (06–18 Normal=1, 18–22 Peak=2, else Off-peak=0, Asia/Kolkata) live in `live_predict.py` and are mirrored in `getTariffCode()` in `app.js`. Change both.
- **Risk cut-offs** in `app.js` (`RISK_MODERATE` 27, `RISK_HIGH` 55, `RISK_VERY_HIGH` 80) come from the output membership functions in `EnergyRisk.fis`. Update them if those change.
- **Fuzzy changes**: edit `build_EnergyRisk.m` and re-run it. Never hand-edit `EnergyRisk.fis`.
- **ANN features**: the order of `FEATURE_NAMES` in `preprocess.py` is baked into the trained model. Changing features means retraining and committing a new `energy_ann.keras` and `preprocessing.json` together.
- **Household IDs** are `MAC` + 6 digits (e.g. `MAC000002`). The UI accepts 2–5567, but the model only knows the households it was trained on.

## ANN data rules (do not break)

- Never replace missing or invalid kWh with 0; drop those rows.
- Split chronologically (train oldest, test newest), never randomly.
- Fit the scaler on training data only.
- Calendar features only; the target is never an input.
- Never modify raw CSV files.

## Conventions

- Keep the frontend minimal: plain HTML and CSS, thin borders, neutral colours, colour only for risk level. No frameworks or CDNs.
- Keep the server bound to 127.0.0.1.
- Do not commit anything in `data/` or any `.csv`/`.pkl`. The small model files in `models/ann/saved_model` and `models/ann/preprocessing` are committed on purpose.
- Python style: standard library first, short docstrings, clear error messages for the UI (the frontend shows `error` text directly).
