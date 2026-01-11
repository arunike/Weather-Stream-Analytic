import numpy as np
from sklearn.ensemble import IsolationForest
import joblib
import os

MODEL_PATH = "src/model/isolation_forest.pkl"

def train_model():
    print("Training Isolation Forest Model...")
    # Generate synthetic "normal" transactions
    # Features: [amount, lat, lon]
    # Normal behavior: Amount < 500, Lat/Lon within typical range (e.g., US/Europe)
    rng = np.random.RandomState(42)
    
    # 1000 normal transactions
    X_train = 0.3 * rng.randn(1000, 3)
    X_train = np.r_[X_train + 2, X_train - 2]
    
    # Add some meaningful scale
    # Amount ~ 50 (scaled), Lat ~ 40, Lon ~ -70
    X_train[:, 0] = X_train[:, 0] * 100 + 50 # Amounts
    X_train[:, 1] = X_train[:, 1] * 10 + 40  # Lat
    X_train[:, 2] = X_train[:, 2] * 10 - 70  # Lon
    
    # Fit the model
    clf = IsolationForest(max_samples=100, random_state=rng, contamination=0.1)
    clf.fit(X_train)
    
    # Save
    joblib.dump(clf, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train_model()
