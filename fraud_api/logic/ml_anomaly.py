from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
import logging

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

MODEL_PATH = (
    Path(__file__).resolve().parents[2] / 'ml_models' / 'isolation_forest.joblib'
)


@dataclass
class AnomalyResult:
    is_anomaly: bool
    score: float
    confidence: float
    metadata: Dict[str, float]


class MLAnomalyDetector:
    def __init__(self, model_path: Path = MODEL_PATH):
        self.model_path = model_path
        self.model = self._load_or_train()

    def score(self, transaction: Dict, context: Dict) -> AnomalyResult:
        features = self._extract_features(transaction, context)
        score = float(self.model.decision_function([features])[0])
        prediction = int(self.model.predict([features])[0])
        is_anomaly = prediction == -1
        confidence = min(1.0, abs(score))

        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=score,
            confidence=confidence,
            metadata={
                'amount': float(features[0]),
                'hour': float(features[1]),
                'recent_count': float(features[2]),
                'avg_amount': float(features[3])
            }
        )

    def _load_or_train(self) -> IsolationForest:
        if self.model_path.exists():
            return joblib.load(self.model_path)

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        model = self._train_default_model()
        joblib.dump(model, self.model_path)
        return model

    def _train_default_model(self) -> IsolationForest:
        rng = np.random.default_rng(42)
        amounts = rng.normal(250.0, 120.0, 800)
        hours = rng.integers(0, 24, 800)
        counts = rng.integers(0, 6, 800)
        avg_amounts = rng.normal(240.0, 90.0, 800)

        training_data = np.column_stack(
            [
                np.abs(amounts),
                hours.astype(float),
                counts.astype(float),
                np.abs(avg_amounts)
            ]
        )

        model = IsolationForest(
            n_estimators=100,
            contamination=0.08,
            random_state=42
        )
        model.fit(training_data)
        logger.info("Trained default Isolation Forest model")
        return model

    @staticmethod
    def _extract_features(transaction: Dict, context: Dict) -> List[float]:
        amount = float(transaction.get('amount', 0.0))
        hour = float(transaction.get('hour', transaction.get('timestamp_hour', 12)))
        recent_txns = context.get('recent_transactions', [])
        recent_count = float(len(recent_txns))
        avg_amount = float(
            sum(t.get('amount', 0.0) for t in recent_txns) / recent_count
        ) if recent_count > 0 else 0.0

        return [amount, hour, recent_count, avg_amount]
