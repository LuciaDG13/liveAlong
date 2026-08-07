"""Trains the distress/mild-crisis text classifier from data/train.csv and
evaluates it against data/eval.csv.

Run from the project root:
    python -m llm.safety_classifier.train

NOTE: as of this draft, train.csv/eval.csv contain no "crisis"-labeled
examples (see data/README.md) -- the resulting model can currently only
distinguish "none" from "mild_distress". This is expected until
mentor-reviewed crisis examples are added.
"""

import csv
import os

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.pipeline import Pipeline

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.joblib")


def load_csv(path):
    texts, labels = [], []
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            texts.append(row["text"])
            labels.append(row["label"])
    return texts, labels


def train():
    train_texts, train_labels = load_csv(os.path.join(DATA_DIR, "train.csv"))
    eval_texts, eval_labels = load_csv(os.path.join(DATA_DIR, "eval.csv"))

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])
    pipeline.fit(train_texts, train_labels)

    predictions = pipeline.predict(eval_texts)
    print("Classes the model can currently predict:", sorted(set(train_labels)))
    print(classification_report(eval_labels, predictions, zero_division=0))

    joblib.dump(pipeline, MODEL_PATH)
    print(f"Saved model to {MODEL_PATH}")


if __name__ == "__main__":
    train()
