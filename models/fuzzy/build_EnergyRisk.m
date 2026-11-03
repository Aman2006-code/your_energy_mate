% build_EnergyRisk.m
% Your Energy Mate - Fuzzy Logic System (EE3055 Soft Computing)
% Builds a Mamdani FIS that maps ConsumptionPct and Tariff to RiskScore
% and saves it as EnergyRisk.fis in the same folder as this script.
%
% Run with:  >> build_EnergyRisk

clear; clc;

%% 1. Create the Mamdani FIS and set the inference methods
fis = mamfis("Name", "EnergyRisk", ...
    "AndMethod", "min", ...                 % AND         : minimum
    "OrMethod", "max", ...                  % OR          : maximum
    "ImplicationMethod", "min", ...         % Implication : minimum
    "AggregationMethod", "max", ...         % Aggregation : maximum
    "DefuzzificationMethod", "centroid");   % Defuzzification : centroid

%% 2. Input 1: ConsumptionPct (0-300 %)
fis = addInput(fis, [0 300], "Name", "ConsumptionPct");
fis = addMF(fis, "ConsumptionPct", "trapmf", [0 0 40 80],     "Name", "Low");
fis = addMF(fis, "ConsumptionPct", "trimf",  [60 100 140],    "Name", "Normal");
fis = addMF(fis, "ConsumptionPct", "trimf",  [120 160 200],   "Name", "High");
fis = addMF(fis, "ConsumptionPct", "trapmf", [180 230 300 300], "Name", "VeryHigh");

%% 3. Input 2: Tariff (0 = OffPeak, 1 = Normal, 2 = Peak)
% Each triangle peaks exactly at its category value (0, 1 or 2).
fis = addInput(fis, [0 2], "Name", "Tariff");
fis = addMF(fis, "Tariff", "trimf", [0 0 1], "Name", "OffPeak");
fis = addMF(fis, "Tariff", "trimf", [0 1 2], "Name", "Normal");
fis = addMF(fis, "Tariff", "trimf", [1 2 2], "Name", "Peak");

%% 4. Output: RiskScore (0-100)
fis = addOutput(fis, [0 100], "Name", "RiskScore");
fis = addMF(fis, "RiskScore", "trapmf", [0 0 15 35],    "Name", "Low");
fis = addMF(fis, "RiskScore", "trimf",  [20 40 60],     "Name", "Moderate");
fis = addMF(fis, "RiskScore", "trimf",  [50 70 90],     "Name", "High");
fis = addMF(fis, "RiskScore", "trapmf", [75 90 100 100], "Name", "VeryHigh");

%% 5. Rule base (12 rules)
% Row format: [Consumption MF, Tariff MF, Risk MF, weight, connector]
% Consumption: 1=Low 2=Normal 3=High 4=VeryHigh
% Tariff     : 1=OffPeak 2=Normal 3=Peak
% Risk       : 1=Low 2=Moderate 3=High 4=VeryHigh
% Connector  : 1 = AND
rules = [ ...
    1 1 1 1 1;   % Low      & OffPeak -> Low
    1 2 1 1 1;   % Low      & Normal  -> Low
    1 3 2 1 1;   % Low      & Peak    -> Moderate
    2 1 1 1 1;   % Normal   & OffPeak -> Low
    2 2 2 1 1;   % Normal   & Normal  -> Moderate
    2 3 3 1 1;   % Normal   & Peak    -> High
    3 1 2 1 1;   % High     & OffPeak -> Moderate
    3 2 3 1 1;   % High     & Normal  -> High
    3 3 4 1 1;   % High     & Peak    -> VeryHigh
    4 1 3 1 1;   % VeryHigh & OffPeak -> High
    4 2 4 1 1;   % VeryHigh & Normal  -> VeryHigh
    4 3 4 1 1];  % VeryHigh & Peak    -> VeryHigh
fis = addRule(fis, rules);

%% 6. Save the FIS next to this script
folder = fileparts(mfilename("fullpath"));
writeFIS(fis, fullfile(folder, "EnergyRisk"));   % creates EnergyRisk.fis
disp("EnergyRisk.fis saved in: " + folder);

%% 7. Test cases (uses evaluateEnergyRisk.m)
tests = [50 0; 100 1; 150 2; 220 2];
disp("Consumption%  Tariff  RiskScore");
for k = 1:size(tests, 1)
    r = evaluateEnergyRisk(tests(k,1), tests(k,2));
    fprintf("%10.2f  %6d  %9.2f\n", tests(k,1), tests(k,2), r);
end

% Check every combination gives a number between 0 and 100
ok = true;
for c = 0:5:300
    for t = [0 1 2]
        r = evaluateEnergyRisk(c, t);
        if isnan(r) || r < 0 || r > 100
            ok = false;
        end
    end
end
disp("All combinations valid (0-100): " + string(ok));

%% Optional viva visuals (uncomment to use)
% plotmf(fis, "input", 1);  plotmf(fis, "input", 2);  plotmf(fis, "output", 1);
% showrule(fis);  gensurf(fis);  ruleview(fis);
