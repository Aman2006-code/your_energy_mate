# Instructions for Claude

This is a college project called **Your Energy Mate**.

## What we are building

A simple household electricity dashboard. It helps a user:
- Enter current household electricity usage.
- See expected usage predicted by an ANN model.
- See whether the current tariff period is peak, normal or off-peak.
- Try switching heavy appliances on and off.
- See a simple electricity-risk recommendation.

## Project structure

- `frontend/` — HTML, CSS and JavaScript UI.
- `backend/` — Python backend and connections between components.
- `models/ann/` — trained Python ANN model and its preprocessing files.
- `models/fuzzy/` — MATLAB fuzzy model files, including `EnergyRisk.fis`.
- `data/` — datasets and sample data.
- `docs/` — project notes and documentation.

## Important decisions

- Keep the project simple. Do not add unnecessary frameworks, packages or features.
- The frontend is planned as plain HTML, CSS and JavaScript.
- The ANN is written in Python.
- The fuzzy system is made in MATLAB.
- The Python backend connects the frontend, ANN and MATLAB fuzzy system.
- AC, iron box and washing machine are treated as equivalent heavy appliances in the frontend simulation. Use the same assumed load increase for all three.
- Appliance switching is simulated. Do not claim that the application physically controls appliances.
- Do not add appliance wattage or sanctioned-load as extra fuzzy inputs.

## Fuzzy system interface

The MATLAB FIS has exactly two inputs and one output:

1. `ConsumptionPct` = actual consumption divided by ANN-predicted consumption, multiplied by 100.
2. `Tariff` = `0` for off-peak, `1` for normal and `2` for peak.
3. `RiskScore` = a numerical risk score from 0 to 100.

The frontend calculates the consumption percentage and selects the tariff code. The Python backend passes those two values to MATLAB and receives the risk score.

If the ANN prediction is zero or unavailable, do not divide by zero or invent a prediction. Show a clear message instead.

## Tariff time windows

The project's current KSEB ToD assumptions are:
- Normal: 6:00 AM to 6:00 PM.
- Peak: 6:00 PM to 10:00 PM.
- Off-peak: 10:00 PM to 6:00 AM.

Keep tariff periods and rates configurable. Do not claim that a tariff applies to every household; its applicability should be checked against the user's connection and the latest KSEB rules.

## When making changes

- First inspect the existing files. Do not assume a folder is already implemented just because it exists.
- Only change the part of the project requested.
- Keep the existing project structure unless there is a clear reason to change it.
- Use sample data only when clearly labelled as sample data.
- Never present mock predictions or mock fuzzy results as real model outputs.
- Keep names and input formats consistent between the frontend, Python backend and MATLAB model.
- Explain briefly what you changed and which parts still use sample data.
