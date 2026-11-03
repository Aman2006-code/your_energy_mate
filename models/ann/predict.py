"""
predict.py - reusable prediction function for the trained ANN.

    from predict import predict_expected_kwh
    kwh = predict_expected_kwh("MAC000002", "2026-11-10 12:30:00")

Command line (from the project root):
    python models/ann/predict.py --household MAC000002 --datetime "2026-11-10 12:30:00"
"""

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from . import preprocess

HERE = Path(__file__).resolve().parent
MODEL_PATH = HERE / "saved_model" / "energy_ann.keras"
PREPROCESSING_PATH = HERE / "preprocessing" / "preprocessing.json"

_model = None       # loaded once and reused
_info = None


class ModelNotAvailableError(Exception):
    """The trained model or its preprocessing file is missing."""


class UnknownHouseholdError(ValueError):
    """The household ID was not in the training data."""


def _load_artifacts():
    """Load the trained ANN and preprocessing info (only the first time)."""
    global _model, _info
    if _model is not None:
        return
    if not MODEL_PATH.exists() or not PREPROCESSING_PATH.exists():
        raise ModelNotAvailableError(
            "Trained model not found. Run train.py first (see README.md).")
    from tensorflow import keras     # imported here so errors above come first
    _model = keras.models.load_model(MODEL_PATH)
    with open(PREPROCESSING_PATH) as file:
        _info = json.load(file)


def predict_expected_kwh(household_id, datetime):
    """Return the expected consumption (kWh) for one 30-minute interval."""
    _load_artifacts()

    # 1. Validate the household ID.
    household_index = _info["household_index"]
    if household_id not in household_index:
        raise UnknownHouseholdError(
            "Unknown household ID '%s'. The model only knows the %d households it was trained on."
            % (household_id, len(household_index)))

    # 2. Validate and convert the date/time.
    try:
        timestamp = pd.Timestamp(datetime)
    except (ValueError, TypeError):
        raise ValueError("Invalid datetime '%s'. Use e.g. '2026-11-10 12:30:00'." % datetime)
    if timestamp.minute not in (0, 30):
        warnings.warn("Training data is half-hourly; the interval of %s is not on :00 or :30."
                      % timestamp)
    if timestamp > pd.Timestamp(_info["training_end"]):
        warnings.warn("%s is after the training data ends (%s). The result is an extrapolation "
                      "from London seasonal/daily patterns." % (timestamp, _info["training_end"]))

    # 3. Same features and scaling as in training.
    features = preprocess.make_time_features([timestamp])
    features = preprocess.apply_scaler(features, np.array(_info["mean"], dtype="float32"),
                                       np.array(_info["std"], dtype="float32"))
    household_number = np.array([[household_index[household_id]]], dtype="int32")

    # 4. Run the trained network.
    output = _model.predict({"household": household_number, "time_features": features}, verbose=0)
    kwh = float(output[0][0])
    return max(kwh, 0.0)         # energy cannot be negative


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict expected half-hourly kWh")
    parser.add_argument("--household", required=True)
    parser.add_argument("--datetime", required=True)
    arguments = parser.parse_args()
    try:
        result = predict_expected_kwh(arguments.household, arguments.datetime)
        print("Expected consumption: %.4f kWh" % result)
    except (ModelNotAvailableError, UnknownHouseholdError, ValueError) as error:
        print("Error: %s" % error)
        raise SystemExit(1)
