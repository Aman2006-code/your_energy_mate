
from datetime import datetime
from zoneinfo import ZoneInfo
import math

from .predict import predict_expected_kwh


TIMEZONE = ZoneInfo("Asia/Kolkata")


def get_fuzzy_inputs(household_id, actual_hourly_kwh, date_time=None):

    actual_hourly_kwh = float(actual_hourly_kwh)

    if not math.isfinite(actual_hourly_kwh) or actual_hourly_kwh < 0:
        raise ValueError("Actual consumption must be a valid non-negative number.")

    if date_time is None:
        date_time = datetime.now(TIMEZONE)
    elif date_time.tzinfo is None:
        date_time = date_time.replace(tzinfo=TIMEZONE)
    else:
        date_time = date_time.astimezone(TIMEZONE)

    hour_start = date_time.replace(
        minute=0,
        second=0,
        microsecond=0
    )

    time_1 = hour_start.replace(tzinfo=None)
    time_2 = hour_start.replace(minute=30, tzinfo=None)

    prediction_1 = predict_expected_kwh(
        household_id,
        time_1.strftime("%Y-%m-%d %H:%M:%S")
    )

    prediction_2 = predict_expected_kwh(
        household_id,
        time_2.strftime("%Y-%m-%d %H:%M:%S")
    )

    expected_hourly_kwh = float(prediction_1 + prediction_2)

    if not math.isfinite(expected_hourly_kwh) or expected_hourly_kwh <= 0:
        raise ValueError("ANN expected consumption is zero or unavailable.")

    consumption_pct = min((
        actual_hourly_kwh / expected_hourly_kwh
    ) * 100,300)

    hour = hour_start.hour

    if 6 <= hour < 18:
        tariff_code = 1
    elif 18 <= hour < 22:
        tariff_code = 2
    else:
        tariff_code = 0

    return [round(float(consumption_pct),2), tariff_code]


if __name__ == "__main__":

    try:
        house_number = int(input("Enter house number (2-5567): "))

        if not 2 <= house_number <= 5567:
            raise ValueError("House number must be between 2 and 5567.")

        household_id = f"MAC{house_number:06d}"

        actual_hourly_kwh = float(
            input("Enter actual hourly consumption (kWh): ")
        )

        result = get_fuzzy_inputs(
            household_id=household_id,
            actual_hourly_kwh=actual_hourly_kwh
        )

        print("\nHousehold:", household_id)
        print("Consumption percentage:", result[0])
        print("Tariff code:", result[1])

    except ValueError as error:
        print("Error:", error)
