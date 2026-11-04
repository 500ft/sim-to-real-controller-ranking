function make_parameter_fit(root, figDir, S)
%MAKE_PARAMETER_FIT Simulator parameter-recovery fit and residual figures.
parameter_fit_figures(fullfile(root, 'runs', 'dynamic_parameter_identification'), ...
    fullfile(figDir, 'dynamic_parameter_fit'), fullfile(figDir, 'dynamic_parameter_residuals'), S);
end
