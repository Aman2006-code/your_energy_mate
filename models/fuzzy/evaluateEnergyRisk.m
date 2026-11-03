function riskScore = evaluateEnergyRisk(consumptionPct, tariff)
% evaluateEnergyRisk  Electricity risk score from the EnergyRisk fuzzy system.
%
%   riskScore = evaluateEnergyRisk(consumptionPct, tariff)
%
%   consumptionPct : consumption as % of expected, 0-300 (from Python ANN)
%   tariff         : 0 = Off-peak, 1 = Normal, 2 = Peak
%   riskScore      : fuzzy risk score, 0-100
%
%   Example: riskScore = evaluateEnergyRisk(106.25, 2);

    % --- Validate inputs ---
    validateattributes(consumptionPct, {'numeric'}, ...
        {'scalar', 'real', 'finite', '>=', 0, '<=', 300}, ...
        mfilename, 'consumptionPct');
    validateattributes(tariff, {'numeric'}, ...
        {'scalar', 'real', 'finite', '>=', 0, '<=', 2}, ...
        mfilename, 'tariff');
    if ~ismember(tariff, [0 1 2])
        error("evaluateEnergyRisk:badTariff", ...
            "tariff must be 0 (Off-peak), 1 (Normal) or 2 (Peak).");
    end

    % --- Load the FIS saved by build_EnergyRisk.m (same folder as this file) ---
    folder = fileparts(mfilename("fullpath"));
    fisFile = fullfile(folder, "EnergyRisk.fis");
    if ~isfile(fisFile)
        error("evaluateEnergyRisk:noFIS", ...
            "EnergyRisk.fis not found. Run build_EnergyRisk first.");
    end
    fis = readfis(fisFile);

    % --- Fuzzify, apply rules, aggregate, defuzzify (all inside evalfis) ---
    riskScore = evalfis(fis, [double(consumptionPct), double(tariff)]);
end
