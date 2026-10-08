import pandas as pd
from sklearn.preprocessing import OneHotEncoder
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix

path = r"D:\SentinelLog-AI\ai-model\dataset\HDFS_2k.log_structured.csv"
df = pd.read_csv(path)

print(f"The size of the dataset :{df.size}")
print(df.shape)
print(df.head(0))


# Map the output
df["Level"] = df["Level"].map({
    "INFO": 0,
    "WARN": 1
})

# Drop columns that are not useful as model features
df = df.drop(columns=["LineId", "Date", "Time", "Pid", "Content", "EventTemplate"])

# Input features
features = ["Component","EventId"]

# Input and output assignment
X = df[features]
y = df["Level"]

encoder = OneHotEncoder(
    handle_unknown="ignore",
    sparse_output=False
)

X_encoded = encoder.fit_transform(X)

# Input and output
X = df[features]
y = df["Level"]

# Split first
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# Fit encoder ONLY on training data
encoder = OneHotEncoder(
    handle_unknown="ignore",
    sparse_output=False
)

X_train_encoded = encoder.fit_transform(X_train)
X_test_encoded = encoder.transform(X_test)

model = LogisticRegression(
    max_iter=1000,
    random_state=42
)

model.fit(X_train_encoded, y_train)

y_pred = model.predict(X_test_encoded)

print(confusion_matrix(y_test, y_pred))
print(classification_report(y_test, y_pred))