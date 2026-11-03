function b = to_bool(x)
%TO_BOOL Logical vector from a CSV column holding True/False text, 0/1 or logicals.
if isstring(x) || iscellstr(x) || ischar(x)
    b = strcmpi(strtrim(string(x)), "true") | strtrim(string(x)) == "1";
else
    b = logical(x);
end
b = b(:);
end
