function render_figures(root, outRoot, only)
%RENDER_FIGURES Draw every MATLAB report figure from committed run files.
%   render_figures()                     repo root inferred from this file; writes in place
%   render_figures(root, outRoot)        read under root, write under outRoot
%   render_figures(root, outRoot, only)  only = cellstr of family names
%
%   Each figure is written as <name>.pdf (vector) and <name>.png (300 dpi) to
%   reports/figures/ or evidence/item11/figures/. The 'tables' family writes
%   LaTeX table fragments to reports/figures/tables/. Run from the repository root:
%       matlab -batch "addpath('experiments/matlab'); render_figures"
%   Captions and the small derived tables come from Python first:
%       PYTHONPATH=gym MPLBACKEND=Agg python experiments/report_figures.py

here = fileparts(mfilename('fullpath'));
if nargin < 1 || isempty(root), root = fileparts(fileparts(here)); end
if nargin < 2 || isempty(outRoot), outRoot = root; end
families = {
    'integrator',       @make_integrator,       'reports'
    'convergence',      @make_convergence,      'reports'
    'dynamic-replay',   @make_dynamic_replay,   'reports'
    'kinematic-replay', @make_kinematic_replay, 'reports'
    'excitation',       @make_excitation,       'reports'
    'parameter-fit',    @make_parameter_fit,    'reports'
    'pure-pursuit',     @make_pure_pursuit,     'reports'
    'ekf',              @make_ekf,              'reports'
    'fmea',             @make_fmea,             'reports'
    'parameter-id',     @make_parameter_id,     'reports'
    'item11',           @make_item11,           'item11'
    'ope-structure',    @make_ope_structure,    'reports'
    'command-response', @make_command_response, 'reports'
    'tables',           @make_tables,           'tables'
};
if nargin < 3 || isempty(only), only = families(:, 1); end
S = fig_style();
dirs.reports = fullfile(outRoot, 'reports', 'figures');
dirs.item11 = fullfile(outRoot, 'evidence', 'item11', 'figures');
dirs.tables = fullfile(outRoot, 'reports', 'figures', 'tables');
failed = 0;
for k = 1:size(families, 1)
    name = families{k, 1};
    if ~any(strcmp(only, name)), continue; end
    figDir = dirs.(families{k, 3});
    if ~exist(figDir, 'dir'), mkdir(figDir); end
    try
        families{k, 2}(root, figDir, S);
        fprintf('OK   %s\n', name);
    catch err
        failed = failed + 1;
        fprintf('FAIL %s: %s\n', name, err.message);
        for s = 1:min(3, numel(err.stack))
            fprintf('     at %s line %d\n', err.stack(s).name, err.stack(s).line);
        end
        close all force;
    end
end
fprintf('%d of %d families failed\n', failed, numel(only));
end
