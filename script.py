from pathlib import Path
import matlab.engine

from models.ann.live_predict import get_fuzzy_inputs

FUZZY_DIR = Path(__file__).resolve().parent / "models" / "fuzzy"

actual_kwh = float(input("Actual hourly consumption (kWh): "))

consumption_pct, tariff = get_fuzzy_inputs('MAC000002', actual_kwh)

eng = matlab.engine.start_matlab()
try:
    eng.addpath(str(FUZZY_DIR), nargout=0)
    risk = eng.evaluateEnergyRisk(float(consumption_pct), float(tariff), nargout=1)
finally:
    eng.quit()

print("Consumption %:", round(float(consumption_pct), 2))
print("Tariff:", tariff)
print("Risk score:", round(float(risk), 2))

