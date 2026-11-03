"""
preprocess.py - data cleaning and feature engineering for the Your Energy Mate ANN.

Both train.py and predict.py import the functions in this file, so training and
prediction always build exactly the same features.
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Order matters: the ANN expects the features in exactly this order.
FEATURE_NAMES = [
    "hour", "minute", "day_of_week", "day_of_month", "month", "day_of_year",
    "is_weekend",
    "hour_sin", "hour_cos", "weekday_sin", "weekday_cos", "month_sin", "month_cos",
]


def find_csv_files(data_dir):
    """Return every .csv file inside data_dir (including sub-folders), in a fixed order."""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise FileNotFoundError("Data folder not found: %s" % data_dir)
    csv_files = sorted(p for p in data_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".csv")
    if not csv_files:
        raise FileNotFoundError("No CSV files found inside %s" % data_dir)
    return csv_files


def _match_columns(csv_path):
    """
    Check that a CSV has the three columns we need and return a rename map
    {name in this file: standard name}. Names are matched ignoring case and
    stray spaces, and the column order in the file does not matter.
    """
    header = pd.read_csv(csv_path, nrows=0)
    by_clean_name = {name.strip().lower(): name for name in header.columns}
    household_col = by_clean_name.get("lclid")
    time_col = by_clean_name.get("datetime")
    kwh_col = next((orig for clean, orig in by_clean_name.items() if clean.startswith("kwh/hh")), None)
    if household_col is None or time_col is None or kwh_col is None:
        raise ValueError(
            "%s has incompatible columns %s. Each file needs LCLid, DateTime and "
            "'KWH/hh (per half hour)'." % (Path(csv_path).name, list(header.columns)))
    return {household_col: "household_id", time_col: "timestamp", kwh_col: "kwh"}


def _folder_signature(csv_files, max_households):
    """Describes the input files, so a saved processed copy is only reused if nothing changed."""
    return {
        "files": [[str(p), p.stat().st_size, p.stat().st_mtime_ns] for p in csv_files],
        "max_households": max_households,
    }


def load_dataset(data_dir, max_households=None, chunk_size=500_000,
                 processed_dir=None, use_cache=True):
    """
    Read ALL csv files in data_dir (in chunks) and combine them into one clean dataset.

    - Every file is checked for the required columns before reading starts.
    - Only the needed columns are loaded. Household IDs are stored as small integer
      codes while loading, which saves a lot of memory on large data.
    - Rows with a missing or non-numeric consumption (e.g. "Null") are DROPPED.
      A missing reading is never replaced by 0.
    - Exact duplicate rows are removed after each file (so repeated/overlapping files
      do not take extra memory); remaining readings that share the same household and
      timestamp are averaged.
    - If max_households is given, only the first N households found (across all files)
      are kept.
    - If processed_dir is given, the cleaned result is saved there and reused next time
      as long as the raw files have not changed. The raw CSV files are never modified.

    Returns (data, summary). data has columns household_id, timestamp, kwh.
    """
    csv_files = find_csv_files(data_dir)
    rename_maps = {path: _match_columns(path) for path in csv_files}   # fail early on bad files

    # Reuse the processed copy if the raw files are unchanged.
    cache_path = Path(processed_dir) / "combined_clean.pkl" if processed_dir else None
    signature = _folder_signature(csv_files, max_households)
    if cache_path is not None and use_cache and cache_path.exists():
        try:
            saved = pd.read_pickle(cache_path)
            if saved["signature"] == signature:
                print("Using processed data from %s" % cache_path)
                return saved["data"], saved["summary"]
        except Exception:
            pass    # unreadable cache: just rebuild it

    household_codes = {}            # household ID -> small integer
    kept_frames = []
    summary = {"files": len(csv_files), "rows_read": 0, "rows_invalid_dropped": 0,
               "exact_duplicates_removed": 0, "same_key_rows_merged": 0}

    for csv_path in csv_files:
        file_frames = []
        reader = pd.read_csv(csv_path, usecols=list(rename_maps[csv_path].keys()),
                             dtype=str, chunksize=chunk_size)
        for chunk in reader:
            chunk = chunk.rename(columns=rename_maps[csv_path])[["household_id", "timestamp", "kwh"]]
            summary["rows_read"] += len(chunk)
            chunk["household_id"] = chunk["household_id"].str.strip()

            # Decide which households we are allowed to keep.
            if max_households is not None:
                for household in chunk["household_id"].dropna().unique():
                    if household not in household_codes and len(household_codes) < max_households:
                        household_codes[household] = len(household_codes)
                chunk = chunk[chunk["household_id"].isin(household_codes)]
                if chunk.empty:
                    continue
            else:
                for household in chunk["household_id"].dropna().unique():
                    household_codes.setdefault(household, len(household_codes))

            chunk["kwh"] = pd.to_numeric(chunk["kwh"], errors="coerce").astype("float32")
            chunk["timestamp"] = pd.to_datetime(chunk["timestamp"], errors="coerce")
            rows_before = len(chunk)
            chunk = chunk.dropna(subset=["household_id", "kwh", "timestamp"])   # drop, never fill with 0
            chunk = chunk[chunk["kwh"] >= 0]                                     # negative energy is invalid
            summary["rows_invalid_dropped"] += rows_before - len(chunk)

            chunk["household_id"] = chunk["household_id"].map(household_codes).astype("int32")
            file_frames.append(chunk)

        if file_frames:
            file_data = pd.concat(file_frames, ignore_index=True)
            rows_before = len(file_data)
            file_data = file_data.drop_duplicates()
            summary["exact_duplicates_removed"] += rows_before - len(file_data)
            kept_frames.append(file_data)
        print("Read %s" % csv_path.name)

    if not kept_frames:
        raise ValueError("No valid rows were found in %s" % data_dir)

    data = pd.concat(kept_frames, ignore_index=True)
    del kept_frames

    # Same household + same timestamp but different values (or repeated across files): average.
    rows_before = len(data)
    data = data.groupby(["household_id", "timestamp"], as_index=False)["kwh"].mean()
    summary["same_key_rows_merged"] = rows_before - len(data)
    data["kwh"] = data["kwh"].astype("float32")

    # Turn the integer codes back into household IDs (stored compactly as a categorical).
    household_names = [None] * len(household_codes)
    for name, code in household_codes.items():
        household_names[code] = name
    data["household_id"] = pd.Categorical.from_codes(data["household_id"].to_numpy(),
                                                     categories=household_names)
    data = data.sort_values("timestamp").reset_index(drop=True)
    summary["rows_final"] = len(data)

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        pd.to_pickle({"signature": signature, "data": data, "summary": summary}, cache_path)
        print("Saved processed data to %s" % cache_path)
    return data, summary


def make_time_features(timestamps):
    """
    Turn timestamps into the numeric temporal features listed in FEATURE_NAMES.
    Only calendar information is used, so these features are always available
    for any future date. Target consumption is never used as an input.
    """
    times = pd.DatetimeIndex(timestamps)
    hour = times.hour.to_numpy()
    minute = times.minute.to_numpy()
    day_of_week = times.dayofweek.to_numpy()      # Monday = 0
    month = times.month.to_numpy()

    # Cyclical encoding: 23:30 and 00:00 are close in time, and so are Dec/Jan.
    fractional_hour = hour + minute / 60.0
    features = pd.DataFrame({
        "hour": hour,
        "minute": minute,
        "day_of_week": day_of_week,
        "day_of_month": times.day.to_numpy(),
        "month": month,
        "day_of_year": times.dayofyear.to_numpy(),
        "is_weekend": (day_of_week >= 5).astype(int),
        "hour_sin": np.sin(2 * np.pi * fractional_hour / 24.0),
        "hour_cos": np.cos(2 * np.pi * fractional_hour / 24.0),
        "weekday_sin": np.sin(2 * np.pi * day_of_week / 7.0),
        "weekday_cos": np.cos(2 * np.pi * day_of_week / 7.0),
        "month_sin": np.sin(2 * np.pi * (month - 1) / 12.0),
        "month_cos": np.cos(2 * np.pi * (month - 1) / 12.0),
    })
    return features[FEATURE_NAMES].to_numpy(dtype="float32")


def chronological_split(data, train_fraction=0.70, validation_fraction=0.15):
    """
    Split by TIME, not randomly: oldest readings -> train, next -> validation,
    newest -> test. This avoids temporal data leakage.
    """
    train_end = data["timestamp"].quantile(train_fraction)
    validation_end = data["timestamp"].quantile(train_fraction + validation_fraction)
    train = data[data["timestamp"] < train_end]
    validation = data[(data["timestamp"] >= train_end) & (data["timestamp"] < validation_end)]
    test = data[data["timestamp"] >= validation_end]
    return train, validation, test


def build_household_index(household_ids):
    """Map each household ID to an integer (used by the embedding layer)."""
    return {household: number for number, household in enumerate(sorted(set(household_ids)))}


def fit_scaler(features):
    """Compute mean and standard deviation on TRAINING data only."""
    mean = features.mean(axis=0)
    std = features.std(axis=0)
    std[std == 0] = 1.0          # avoid dividing by zero for constant columns
    return mean, std


def apply_scaler(features, mean, std):
    """Standardise features using the saved mean/std."""
    return ((features - mean) / std).astype("float32")
