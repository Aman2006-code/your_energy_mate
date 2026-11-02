# Your Energy Mate

A simple household energy management project using an **Artificial Neural Network (ANN)** and **Fuzzy Logic**.

## What it does

- Takes the household's current electricity usage.
- Predicts expected usage using an ANN model.
- Identifies the current electricity tariff period.
- Lets the user simulate switching heavy appliances on and off.
- Uses fuzzy logic to produce an electricity-risk score and recommendation.

## How it works

1. The user enters current household usage and selects a date/time and location.
2. The Python ANN predicts expected consumption for the selected time interval.
3. The frontend compares actual usage with predicted usage.
4. The tariff module identifies the current tariff period.
5. The frontend sends the consumption percentage and tariff category to the Python backend.
6. The backend asks the MATLAB Fuzzy Inference System (FIS) for a risk score.
7. The dashboard displays the score and a simple recommendation.

## Appliance simulation

AC, iron box and washing machine are treated as equivalent heavy appliances. Switching any of them on applies the same assumed load increase in the frontend simulation. These switches do not control real appliances.

## Fuzzy system inputs and output

The MATLAB FIS uses two inputs:

| Input | Meaning |
|---|---|
| `ConsumptionPct` | Actual consumption / ANN-predicted consumption × 100 |
| `Tariff` | `0` = off-peak, `1` = normal, `2` = peak |

It returns one output:

| Output | Meaning |
|---|---|
| `RiskScore` | Risk score from 0 to 100 |

If the ANN prediction is zero or unavailable, the consumption percentage cannot be calculated. The application should show an appropriate message instead of producing a false result.

## Tariff time periods

The current project configuration uses these KSEB Time of Day periods:

- **Normal:** 6:00 AM–6:00 PM
- **Peak:** 6:00 PM–10:00 PM
- **Off-peak:** 10:00 PM–6:00 AM

Keep tariff rates configurable. Check the latest KSEB tariff order and the household's eligibility before presenting these periods or rates as applicable to a real connection.

## Project structure

```text
your_energy_mate/
├── frontend/           # HTML, CSS and JavaScript dashboard
│   ├── assets/
│   └── js/
├── backend/            # Python backend
│   ├── ann/             # ANN-related backend logic
│   ├── fuzzy/           # MATLAB connection
│   ├── services/        # Shared backend services
│   └── tariff/          # Tariff period and cost calculations
├── models/
│   ├── ann/             # Trained ANN model and preprocessing
│   └── fuzzy/           # MATLAB .m and .fis files
├── data/
│   ├── raw/
│   ├── processed/
│   └── sample/
└── docs/                # Project documentation
```

## Current development status

The folders are the planned project structure. Add the frontend, backend, trained ANN and MATLAB FIS files as they are completed. Clearly label demonstration data until the real models are connected.

## Team note

Keep the frontend, ANN, tariff logic and fuzzy model separate. Agree on units and input formats before integration. Keep the implementation small and understandable.
