# Observation in the HDFS Dataset

Total Data present in the Dataset : 18000
Rows X Columns : (2000, 9)
Columns: [LineId, Date, Time, Pid, Level, Component, Content, EventId, EventTemplate]

Now from the above LineId, Date, Time, Pid dosent play important role in model creating so drop the following

Reamining column
Columns: [Level, Component, Content, EventId, EventTemplate]
