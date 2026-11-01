%% Smart Household Energy Management System - Fuzzy Risk Scoring (Mamdani)
% Requires: MATLAB Fuzzy Logic Toolbox (R2018b or newer)
%
% Inputs : 1) ConsumptionPct  (0-250 %)   = Actual / ANN Predicted * 100
%          2) Tariff          (0, 1, 2)   = Off-peak, Normal, Peak
% Output : RiskScore          (0-100)
%
% Run this script once: it builds the FIS, saves 'EnergyRisk.fis',
% draws the plots/viewers and prints five test scenarios.

clear; clc; close all;

%% 1. Create the Mamdani FIS (centroid defuzzification)
fis = mamfis('Name', 'EnergyRisk', ...
    'AndMethod', 'min', 'OrMethod', 'max', ...
    'ImplicationMethod', 'min', 'AggregationMethod', 'max', ...
    'DefuzzificationMethod', 'centroid');

%% 2. Input 1: Actual Consumption Percentage (0-250)
fis = addInput(fis, [0 250], 'Name', 'ConsumptionPct');
fis = addMF(fis, 'ConsumptionPct', 'trapmf', [0 0 60 100],     'Name', 'BelowExpected');
fis = addMF(fis, 'ConsumptionPct', 'trimf',  [60 100 140],     'Name', 'Normal');
fis = addMF(fis, 'ConsumptionPct', 'trapmf', [100 140 250 250],'Name', 'AboveExpected');

%% 3. Input 2: Electricity Tariff (0 = Off-peak, 1 = Normal, 2 = Peak)
fis = addInput(fis, [0 2], 'Name', 'Tariff');
fis = addMF(fis, 'Tariff', 'trimf', [0 0 1], 'Name', 'OffPeak');
fis = addMF(fis, 'Tariff', 'trimf', [0 1 2], 'Name', 'Normal');
fis = addMF(fis, 'Tariff', 'trimf', [1 2 2], 'Name', 'Peak');

%% 4. Output: Energy Consumption Risk Score (0-100)
fis = addOutput(fis, [0 100], 'Name', 'RiskScore');
fis = addMF(fis, 'RiskScore', 'trapmf', [0 0 20 40],    'Name', 'LowRisk');
fis = addMF(fis, 'RiskScore', 'trimf',  [25 50 75],     'Name', 'ModerateRisk');
fis = addMF(fis, 'RiskScore', 'trapmf', [60 80 100 100],'Name', 'HighRisk');

%% 5. Nine rules
% Columns: [Consumption MF, Tariff MF, Risk MF, weight, AND(1)]
% Consumption: 1=Below 2=Normal 3=Above | Tariff: 1=Off 2=Normal 3=Peak
% Risk:        1=Low   2=Moderate 3=High
rules = [ ...
    1 1 1 1 1;   % Below  & OffPeak -> Low
    1 2 1 1 1;   % Below  & Normal  -> Low
    1 3 2 1 1;   % Below  & Peak    -> Moderate
    2 1 1 1 1;   % Normal & OffPeak -> Low
    2 2 2 1 1;   % Normal & Normal  -> Moderate
    2 3 2 1 1;   % Normal & Peak    -> Moderate
    3 1 2 1 1;   % Above  & OffPeak -> Moderate
    3 2 3 1 1;   % Above  & Normal  -> High
    3 3 3 1 1];  % Above  & Peak    -> High
fis = addRule(fis, rules);

%% 6. Save the FIS file
writeFIS(fis, 'EnergyRisk');          % creates EnergyRisk.fis
disp('Saved: EnergyRisk.fis');

%% 7. Membership function plots
figure('Name', 'Membership Functions', 'Position', [100 100 900 700]);
subplot(3,1,1); plotmf(fis, 'input', 1);  title('Input 1: Consumption Percentage');
subplot(3,1,2); plotmf(fis, 'input', 2);  title('Input 2: Tariff (0=Off-peak, 1=Normal, 2=Peak)');
subplot(3,1,3); plotmf(fis, 'output', 1); title('Output: Risk Score');

%% 8. Rule viewer and surface viewer
ruleview(fis);                         % interactive rule viewer
figure('Name', 'Surface Viewer');
gensurf(fis);                          % 3-D surface
xlabel('Consumption %'); ylabel('Tariff'); zlabel('Risk Score');

%% 9. Five test scenarios
% Each row: [Consumption %, Tariff]
tests = [ ...
     50  0;    % much lower than expected, off-peak
     95  1;    % close to expected, normal tariff
    100  2;    % as expected, peak tariff
    130  1;    % higher than expected, normal tariff
    200  2];   % far above expected, peak tariff

fprintf('\n%-6s %-12s %-8s %-s\n', 'Case', 'Consumption%', 'Tariff', 'RiskScore');
for k = 1:size(tests,1)
    score = energyRisk(fis, tests(k,1), tests(k,2));
    fprintf('%-6d %-12.0f %-8d %.2f\n', k, tests(k,1), tests(k,2), score);
end

%% 10. Evaluation function (use this from Python as well)
% Python (MATLAB Engine API) example:
%   import matlab.engine
%   eng = matlab.engine.start_matlab()
%   fis = eng.readfis('EnergyRisk.fis')
%   score = eng.evalfis(fis, matlab.double([[130.0, 1.0]]))   # [pct, tariff]
function score = energyRisk(fis, consumptionPct, tariff)
    consumptionPct = min(max(consumptionPct, 0), 250);  % keep inside input range
    tariff         = min(max(tariff, 0), 2);
    score = evalfis(fis, [consumptionPct, tariff]);
end
