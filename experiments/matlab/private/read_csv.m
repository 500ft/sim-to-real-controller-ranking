function T = read_csv(path)
%READ_CSV Committed CSV as a table with original column names and string text.
opts = detectImportOptions(path, 'TextType', 'string', 'VariableNamingRule', 'preserve');
T = readtable(path, opts);
end
