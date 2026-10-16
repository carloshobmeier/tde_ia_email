import hashlib
import json
import threading
from collections import Counter
import joblib
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from .config import MODEL_PATH, CATEGORIES, PRIORITIES
from .corpus import bootstrap_samples
from .db import connect, rows, now, set_setting

_model = None
_lock = threading.RLock()


def partition(group):
    bucket = int(hashlib.sha256(group.encode()).hexdigest()[:8], 16) % 10
    return "test" if bucket < 2 else "validation" if bucket < 4 else "train"


def pipeline(kind):
    classifiers = {
        "Regressão logística": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
        "Naive Bayes": MultinomialNB(alpha=0.5),
        "SVM linear": LinearSVC(class_weight="balanced", random_state=42),
        "Classe majoritária": DummyClassifier(strategy="most_frequent"),
    }
    return Pipeline([("tfidf", TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode", sublinear_tf=True, max_features=18000)),
                     ("clf", classifiers[kind])])


def train():
    global _model
    with _lock:
        with connect() as db:
            for sample in bootstrap_samples():
                db.execute("INSERT OR IGNORE INTO samples VALUES (:id,:text,:category,:priority,:group_id,:source)", sample)
        samples = rows("SELECT * FROM samples")
        # Correções nunca alteram exemplos dos conjuntos congelados de avaliação.
        feedback = rows("SELECT text,category,priority,group_id FROM feedback")
        known_texts = {hashlib.sha256(s["text"].strip().lower().encode()).hexdigest() for s in samples}
        train_feedback = [s for s in feedback if partition(s["group_id"]) == "train"
                          and hashlib.sha256(s["text"].strip().lower().encode()).hexdigest() not in known_texts]
        groups = {part: [s for s in samples if partition(s["group_id"]) == part]
                  for part in ["train", "validation", "test"]}
        groups["train"].extend(train_feedback)
        fitted, reports, comparisons = {}, {}, []
        for target, labels in [("category", CATEGORIES), ("priority", PRIORITIES)]:
            candidates = []
            for kind in ["Regressão logística", "Naive Bayes", "SVM linear", "Classe majoritária"]:
                model = pipeline(kind)
                model.fit([s["text"] for s in groups["train"]], [s[target] for s in groups["train"]])
                predicted = model.predict([s["text"] for s in groups["validation"]])
                score = f1_score([s[target] for s in groups["validation"]], predicted, labels=labels,
                                 average="macro", zero_division=0)
                comparisons.append({"task": target, "model": kind, "validation_f1": round(float(score), 4)})
                if kind != "Classe majoritária":
                    candidates.append((score, kind, model))
            _, kind, model = max(candidates, key=lambda c: c[0])
            fitted[target] = model
            y_true = [s[target] for s in groups["test"]]
            y_pred = model.predict([s["text"] for s in groups["test"]])
            reports[target] = {"model": kind, "labels": labels,
                               "report": classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0),
                               "confusion": confusion_matrix(y_true, y_pred, labels=labels).tolist()}
        report = {"trained_at": now(), "synthetic": sum(s["source"] == "synthetic" for s in samples),
                  "imported": sum(s["source"] != "synthetic" for s in samples),
                  "feedback_used": len(train_feedback), "splits": {p: len(g) for p, g in groups.items()},
                  "distribution": dict(Counter(s["category"] for s in samples)),
                  "results": reports, "comparisons": comparisons,
                  "evaluation_scope": "synthetic" if all(s["source"] == "synthetic" for s in samples) else "mixed",
                  "note": "Partições fixas por grupo. Seleção na validação; métricas finais no teste. Corpus inicial sintético: não comprova desempenho em e-mails reais."}
        fitted["version"] = report["trained_at"]
        tmp = MODEL_PATH.with_suffix(".tmp")
        joblib.dump(fitted, tmp)
        tmp.replace(MODEL_PATH)
        _model = fitted
        set_setting("ml_report", report)
        return report


def get_model():
    global _model
    with _lock:
        if _model is None:
            if MODEL_PATH.exists():
                _model = joblib.load(MODEL_PATH)
            else:
                train()
        return _model


def classify(subject, body):
    models = get_model()
    text = f"{subject}\n{body[:24000]}"
    category = str(models["category"].predict([text])[0])
    priority = str(models["priority"].predict([text])[0])
    pipe = models["priority"]
    clf = pipe.named_steps["clf"]
    confidence = float(max(pipe.predict_proba([text])[0])) if hasattr(clf, "predict_proba") else 0.0
    vector = pipe.named_steps["tfidf"].transform([text])
    signals = []
    if hasattr(clf, "coef_"):
        class_index = list(clf.classes_).index(priority)
        coefficients = clf.coef_[class_index]
        values = vector.toarray()[0] * coefficients
        names = pipe.named_steps["tfidf"].get_feature_names_out()
        signals = [str(names[i]) for i in np.argsort(values)[::-1][:4] if values[i] > 0]
    return {"category": category, "priority": priority, "confidence": confidence, "signals": json.dumps(signals)}
