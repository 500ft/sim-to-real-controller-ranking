function m = metric_struct(path)
%METRIC_STRUCT metric,value CSV as a struct of doubles.
T = read_csv(path);
m = struct();
for i = 1:height(T)
    m.(matlab.lang.makeValidName(char(T.metric(i)))) = double(T.value(i));
end
end
