function s = span_of(x)
%SPAN_OF Max minus min (base MATLAB; range() needs a toolbox).
s = max(x(:)) - min(x(:));
end
