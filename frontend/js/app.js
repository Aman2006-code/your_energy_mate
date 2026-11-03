const usageSlider = document.getElementById("usage");
const usageValue = document.getElementById("usageValue");

const baseUsageDisplay = document.getElementById("baseUsage");
const addedUsageDisplay = document.getElementById("addedUsage");
const projectedUsageDisplay = document.getElementById("projectedUsage");

const baseRiskUsage = document.getElementById("baseRiskUsage");
const projectedRiskUsage = document.getElementById("projectedRiskUsage");

const baseRisk = document.getElementById("baseRisk");
const projectedRisk = document.getElementById("projectedRisk");

const baseStatus = document.getElementById("baseStatus");
const projectedStatus = document.getElementById("projectedStatus");

const houseNumberInput = document.getElementById("houseNumber");

const adviceBox = document.getElementById("advice");
const adviceLabel = document.getElementById("adviceLabel");
const adviceMessage = document.getElementById("adviceMessage");

const appliances = {
  ac: 1.000,
  washing: 0.375,
  iron: 0.250
};

const applianceNames = {
  ac: "Air Conditioner",
  washing: "Washing Machine",
  iron: "Iron Box"
};

let updateTimer = null;
let requestVersion = 0;

/* ---------- Risk levels (from the EnergyRisk fuzzy system, output 0-100) ----------
   Output MF centroids are roughly Low ~14, Moderate 40, High 70, VeryHigh ~91,
   so the cut-offs sit midway between them. */
const RISK_MODERATE = 27;
const RISK_HIGH = 55;
const RISK_VERY_HIGH = 80;

const LEVEL_LABELS = ["Low risk", "Moderate risk", "High risk", "Very high risk"];
const LEVEL_STYLES = ["low", "mid", "high", "high"];

function getRiskLevel(score) {
  if (score >= RISK_VERY_HIGH) return 3;
  if (score >= RISK_HIGH) return 2;
  if (score >= RISK_MODERATE) return 1;
  return 0;
}

/* ---------- Tariff (same hours as live_predict.py, India time) ---------- */
function getTariffCode() {
  const hour = Number(
    new Intl.DateTimeFormat("en-GB", {
      hour: "numeric",
      hourCycle: "h23",
      timeZone: "Asia/Kolkata"
    }).format(new Date())
  );

  if (hour >= 6 && hour < 18) return 1; // Normal
  if (hour >= 18 && hour < 22) return 2; // Peak
  return 0; // Off-peak
}

/* ---------- Advice ---------- */
function setAdvice(level, label, message) {
  adviceBox.dataset.level = level;
  adviceLabel.textContent = label;
  adviceMessage.textContent = message;
}

function joinNames(ids) {
  const names = ids.map(id => applianceNames[id]);
  if (names.length <= 1) return names.join("");
  return names.slice(0, -1).join(", ") + " and " + names[names.length - 1];
}

function updateAdvice(baseScore, projectedScore) {
  if (!Number.isFinite(baseScore) && !Number.isFinite(projectedScore)) {
    setAdvice("none", "", "Risk could not be calculated right now.");
    return;
  }

  const projected = Number.isFinite(projectedScore) ? projectedScore : baseScore;
  const base = Number.isFinite(baseScore) ? baseScore : projectedScore;

  const baseLevel = getRiskLevel(base);
  const level = getRiskLevel(projected);
  const tariff = getTariffCode();
  const peak = tariff === 2;
  const offPeak = tariff === 0;

  // Appliances currently on, biggest consumer first.
  const on = Object.keys(appliances)
    .filter(id => document.getElementById(id).checked)
    .sort((a, b) => appliances[b] - appliances[a]);

  const list = joinNames(on);
  const biggest = on.length ? applianceNames[on[0]] : "";
  const word = level === 3 ? "very high" : "high";
  const peakNote = peak ? " Peak tariff is active." : "";

  let message;

  if (on.length === 0) {
    // Only the base load matters.
    if (level === 3) {
      message = "Consumption is already very high. Cut back usage now." + peakNote;
    } else if (level === 2) {
      message = "Consumption is already high. Reduce usage now." + peakNote;
    } else if (level === 1) {
      message = peak
        ? "Consumption is moderate and it's peak tariff time. Avoid adding heavy appliances."
        : "Consumption is moderate. Avoid adding heavy appliances.";
    } else if (offPeak) {
      message = "Consumption is low and it's off-peak. A good time to run appliances.";
    } else if (peak) {
      message = "Consumption is low, but it's peak tariff time. Use appliances sparingly.";
    } else {
      message = "Consumption is low. You can use your appliances.";
    }
  } else if (level >= 2) {
    if (baseLevel >= 2) {
      // Already high before adding anything.
      const toTurnOff = level === 3 ? list : biggest;
      message = `Consumption is already ${word}. Turn off the ${toTurnOff} now.` + peakNote;
    } else if (on.length > 1) {
      message = `Running the ${list} together pushes risk to ${word}. Turn off the ${biggest} now.` + peakNote;
    } else {
      message = `Running the ${biggest} pushes risk to ${word}. Turn it off now.` + peakNote;
    }
  } else if (level === 1) {
    if (on.length > 1) {
      message = `Running the ${list} together raises your risk. Turn off the ${biggest} or run them one at a time.`;
    } else {
      message = peak
        ? `The ${biggest} adds to your load during peak tariff. Wait until off-peak hours.`
        : `The ${biggest} adds to your load. Consider using it a little later.`;
    }
  } else {
    message = `It's safe to run the ${list}.`;
    if (peak) message += " Peak tariff is on, so keep it short.";
    else if (offPeak) message += " Off-peak hours, so it's cheaper too.";
  }

  setAdvice(LEVEL_STYLES[level], LEVEL_LABELS[level], message);
}

/* ---------- Inputs ---------- */
function getHouseholdId() {
  const raw = houseNumberInput.value.trim();
  const number = Number(raw);

  if (raw === "" || !Number.isInteger(number) || number < 2 || number > 5567) {
    throw new Error("Enter a valid house number between 2 and 5567.");
  }

  return "MAC" + String(number).padStart(6, "0");
}

// Convert slider position into actual kWh.
function getUsage(position) {
  const p = Number(position);
  let value;

  if (p <= 180) {
    value = (p / 180) * 0.9;
  } else {
    value = 0.9 + ((p - 180) / 70) * 1.6;
  }

  return Math.round(value * 1000) / 1000;
}

// Additional appliance consumption.
function getAddedUsage() {
  let total = 0;

  for (const [id, consumption] of Object.entries(appliances)) {
    if (document.getElementById(id).checked) {
      total += consumption;
    }
  }

  return Math.round(total * 1000) / 1000;
}

// Update consumption values immediately.
function updateSummary() {
  const base = getUsage(usageSlider.value);
  const added = getAddedUsage();
  const projected = Math.round((base + added) * 1000) / 1000;

  usageValue.textContent = base.toFixed(3);

  baseUsageDisplay.textContent = base.toFixed(3);
  addedUsageDisplay.textContent = added.toFixed(3);
  projectedUsageDisplay.textContent = projected.toFixed(3);

  baseRiskUsage.textContent = base.toFixed(3);
  projectedRiskUsage.textContent = projected.toFixed(3);

  return { base, projected };
}

/* ---------- Backend ---------- */
async function fetchRisk(actualKwh, householdId) {
  const response = await fetch("/api/risk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actual_kwh: actualKwh,
      household_id: householdId
    })
  });

  let data = {};
  try {
    data = await response.json();
  } catch (_) {
    // non-JSON response; handled below
  }

  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }

  return data;
}

function showResult(result, riskEl, statusEl) {
  if (result.status === "fulfilled") {
    riskEl.textContent = Number(result.value.risk_score).toFixed(2);
    statusEl.textContent = "Calculation complete";
  } else {
    riskEl.textContent = "Unavailable";
    statusEl.textContent = result.reason.message;
  }
}

// Calculate both risk scores independently.
async function calculateRisks(base, projected, version, householdId) {
  const results = await Promise.allSettled([
    fetchRisk(base, householdId),
    fetchRisk(projected, householdId)
  ]);

  // Ignore outdated responses if the user changed the inputs.
  if (version !== requestVersion) return;

  showResult(results[0], baseRisk, baseStatus);
  showResult(results[1], projectedRisk, projectedStatus);

  const score = r => (r.status === "fulfilled" ? Number(r.value.risk_score) : NaN);
  updateAdvice(score(results[0]), score(results[1]));
}

// Runs on every input change.
function handleInputChange() {
  const { base, projected } = updateSummary();

  clearTimeout(updateTimer);
  const version = ++requestVersion;

  let householdId;
  try {
    householdId = getHouseholdId();
  } catch (error) {
    baseRisk.textContent = "--";
    projectedRisk.textContent = "--";
    baseStatus.textContent = error.message;
    projectedStatus.textContent = error.message;
    setAdvice("none", "", "Enter your house number");
    return;
  }

  baseStatus.textContent = "Calculating...";
  projectedStatus.textContent = "Calculating...";
  setAdvice("none", "", "Calculating...");

  // Debounce backend calls.
  updateTimer = setTimeout(() => {
    calculateRisks(base, projected, version, householdId);
  }, 400);
}

houseNumberInput.addEventListener("input", handleInputChange);
usageSlider.addEventListener("input", handleInputChange);

Object.keys(appliances).forEach(id => {
  document.getElementById(id).addEventListener("change", handleInputChange);
});

// Initial calculation when the page loads.
handleInputChange();
