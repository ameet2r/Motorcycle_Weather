import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import joblib
import matplotlib.pyplot as plt

# 1. Load the expert-vetted data
df = pd.read_csv('syntheticRideScoreData.csv')

# 2. Separate Features and Target
X = df.drop('ride_score', axis=1)
y = df['ride_score']

# 3. Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 4. Train XGBoost
# We're using slightly more 'estimators' to capture the complex multiplier logic
model = xgb.XGBRegressor(
    n_estimators=200,
    learning_rate=0.05,
    max_depth=6,
    random_state=42
)

model.fit(X_train, y_train)

# 5. Validation
predictions = model.predict(X_test)
mae = mean_absolute_error(y_test, predictions)
print(f"Model Training Complete! Average Error: {mae:.2f} points")

# 6. Feature Importance - See what's driving the score
importances = model.feature_importances_
feature_names = X.columns
for name, imp in zip(feature_names, importances):
    print(f"Feature: {name:15} Importance: {imp:.4f}")

# 7. Save the "Brain"
joblib.dump(model, 'ride_quality_model_v2.joblib')