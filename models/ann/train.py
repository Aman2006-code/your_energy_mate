"""
train.py - trains the MLP (backpropagation) that predicts half-hourly kWh.

Run from the project root:
    python models/ann/train.py --data-dir data/raw/
"""

import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

import preprocess

HERE = Path(__file__).resolve().parent
MODEL_PATH = HERE / "saved_model" / "energy_ann.keras"
PREPROCESSING_PATH = HERE / "preprocessing" / "preprocessing.json"


def build_model(number_of_households, number_of_features, embedding_size=8):
    """
    Household ID -> embedding, joined with the scaled time features, then:
        Dense(64, ReLU) -> Dense(32, ReLU) -> Dense(1, linear)
    """
    household_input = keras.Input(shape=(1,), name="household")
    feature_input = keras.Input(shape=(number_of_features,), name="time_features")

    household_vector = layers.Embedding(number_of_households, embedding_size)(household_input)
    household_vector = layers.Flatten()(household_vector)

    x = layers.Concatenate()([household_vector, feature_input])
    x = layers.Dense(64, activation="relu")(x)
    x = layers.Dense(32, activation="relu")(x)
    output = layers.Dense(1, activation="linear", name="predicted_kwh")(x)

    model = keras.Model(inputs=[household_input, feature_input], outputs=output)
    # Adam optimiser + MSE loss; Keras computes gradients by backpropagation.
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=0.001),
                  loss="mse", metrics=["mae"])
    return model


def to_model_inputs(table, household_index, mean, std):
    """Convert a DataFrame split into the two arrays the model expects."""
    household_numbers = table["household_id"].map(household_index).to_numpy(dtype="int32")
    features = preprocess.apply_scaler(preprocess.make_time_features(table["timestamp"]), mean, std)
    return {"household": household_numbers.reshape(-1, 1), "time_features": features}


def main():
    parser = argparse.ArgumentParser(description="Train the Your Energy Mate ANN")
    parser.add_argument("--data-dir", default="data/raw/",
                        help="folder containing all the raw CSV files")
    parser.add_argument("--processed-dir", default="data/processed/",
                        help="where the cleaned, combined data is saved for reuse")
    parser.add_argument("--no-cache", action="store_true",
                        help="ignore any saved processed data and rebuild it")
    parser.add_argument("--max-households", type=int, default=0,
                        help="use only the first N households (0 = all; needs lots of RAM)")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=1024)
    args = parser.parse_args()

    tf.keras.utils.set_random_seed(42)       # reproducible results
    max_households = args.max_households or None

    print("Loading and cleaning data from %s ..." % args.data_dir)
    data, summary = preprocess.load_dataset(args.data_dir, max_households=max_households,
                                            processed_dir=args.processed_dir,
                                            use_cache=not args.no_cache)
    print("CSV files read:                  %d" % summary["files"])
    print("Rows read:                       %d" % summary["rows_read"])
    print("Rows dropped (missing/invalid):  %d" % summary["rows_invalid_dropped"])
    print("Exact duplicate rows removed:    %d" % summary["exact_duplicates_removed"])
    print("Same household+time rows merged: %d" % summary["same_key_rows_merged"])
    print("Rows after cleaning:             %d" % summary["rows_final"])
    print("Date range: %s to %s" % (data["timestamp"].min(), data["timestamp"].max()))

    train, validation, test = preprocess.chronological_split(data)

    # Only households seen in training have a trained embedding.
    household_index = preprocess.build_household_index(train["household_id"])
    validation = validation[validation["household_id"].isin(household_index)]
    test = test[test["household_id"].isin(household_index)]

    # Scaling statistics come from the training set only.
    mean, std = preprocess.fit_scaler(preprocess.make_time_features(train["timestamp"]))

    x_train = to_model_inputs(train, household_index, mean, std)
    x_val = to_model_inputs(validation, household_index, mean, std)
    x_test = to_model_inputs(test, household_index, mean, std)
    y_train = train["kwh"].to_numpy()
    y_val = validation["kwh"].to_numpy()
    y_test = test["kwh"].to_numpy()

    print("\nTraining records:   %d" % len(train))
    print("Validation records: %d" % len(validation))
    print("Test records:       %d" % len(test))
    print("Unique households:  %d" % len(household_index))

    model = build_model(len(household_index), len(preprocess.FEATURE_NAMES))
    model.summary()

    early_stop = keras.callbacks.EarlyStopping(monitor="val_loss", patience=4,
                                               restore_best_weights=True)
    history = model.fit(x_train, y_train, validation_data=(x_val, y_val),
                        epochs=args.epochs, batch_size=args.batch_size,
                        callbacks=[early_stop], verbose=2)

    # Evaluate on the newest, unseen data.
    predictions = model.predict(x_test, batch_size=4096, verbose=0).ravel()
    test_mae = float(np.mean(np.abs(predictions - y_test)))
    test_rmse = float(np.sqrt(np.mean((predictions - y_test) ** 2)))
    baseline_mae = float(np.mean(np.abs(y_train.mean() - y_test)))   # "always guess the average"

    final_train_loss = float(history.history["loss"][-1])
    best_val_loss = float(min(history.history["val_loss"]))
    print("\nFinal training loss (MSE):   %.6f" % final_train_loss)
    print("Best validation loss (MSE):  %.6f" % best_val_loss)
    print("Test MAE:                    %.4f kWh" % test_mae)
    print("Test RMSE:                   %.4f kWh" % test_rmse)
    print("(Baseline MAE if always predicting the training mean: %.4f kWh)" % baseline_mae)

    # Save the model and everything predict.py needs.
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREPROCESSING_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_PATH)
    info = {
        "feature_names": preprocess.FEATURE_NAMES,
        "mean": mean.tolist(),
        "std": std.tolist(),
        "household_index": household_index,
        "training_start": str(data["timestamp"].min()),
        "training_end": str(data["timestamp"].max()),
        "metrics": {"train_loss": final_train_loss, "val_loss": best_val_loss,
                    "test_mae": test_mae, "test_rmse": test_rmse,
                    "baseline_mae": baseline_mae,
                    "n_train": len(train), "n_val": len(validation), "n_test": len(test)},
    }
    with open(PREPROCESSING_PATH, "w") as file:
        json.dump(info, file, indent=2)
    print("\nSaved model to %s" % MODEL_PATH)
    print("Saved preprocessing to %s" % PREPROCESSING_PATH)


if __name__ == "__main__":
    main()
