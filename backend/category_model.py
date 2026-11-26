"""Load the packaged classifier for advisory requirement categorization."""

from pathlib import Path

import joblib


MODEL_PATH = Path(__file__).with_name("category_model.joblib")
model = joblib.load(MODEL_PATH)


def classify_requirement(description):
    return {
        "category": str(model.predict([description])[0]),
        "method": "trained_tfidf_logistic_regression",
    }
