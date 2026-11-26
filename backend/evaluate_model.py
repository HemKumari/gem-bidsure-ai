"""Re-evaluate the packaged model on the supplied held-out split."""

import json
import sqlite3
from pathlib import Path

from sklearn.metrics import classification_report

from category_model import model


root = Path(__file__).parent
with sqlite3.connect((root / "training.sqlite").resolve().as_uri() + "?mode=ro", uri=True) as db:
    training_rows = db.execute("SELECT COUNT(*) FROM examples WHERE split = 'train'").fetchone()[0]
    examples = db.execute("SELECT text, label FROM examples WHERE split = 'test' ORDER BY text").fetchall()

descriptions, labels = zip(*examples)
report = {
    "training_rows": training_rows,
    "test_rows": len(examples),
    "dataset": "Synthetic held-out templates. Subject terms occur in both splits.",
    "metrics": classification_report(labels, model.predict(descriptions), output_dict=True, zero_division=0),
}
print(json.dumps(report, indent=2))
