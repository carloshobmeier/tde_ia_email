"""TF-IDF + Qev ensemble on the Foco corpus. Run with the project's .venv:
  .venv/bin/python experiments/qev/ensemble_eval.py --qev-probs <qev-probs.json> --out <report.json>

Protocol: TF-IDF trains on the train split exactly like backend.ml.train. Every ensemble
weight, threshold and the choice of method are selected on validation only; the test
split is read once, for the final report. The other methods' test scores are listed for
transparency, not for selection.
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("FOCO_DATA_DIR", tempfile.mkdtemp(prefix="foco-ensemble-"))  # never the personal DB
sys.path.insert(0, str(ROOT))
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import confusion_matrix, f1_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402
from backend.config import CATEGORIES, PRIORITIES  # noqa: E402
from backend.corpus import CORPUS_VERSION, bootstrap_samples, partition  # noqa: E402
from backend.ml import pipeline  # noqa: E402

LABELS = {"category": CATEGORIES, "priority": PRIORITIES}
EPS = 1e-6
ALPHAS = [round(a, 2) for a in np.arange(0, 1.0001, 0.05)]


def macro_f1(y_true, y_pred, labels):
    return float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))


def tfidf_probabilities(task, groups):
    """Same candidates and validation selection as backend.ml.train."""
    labels, best = LABELS[task], None
    for kind in ["Regressão logística", "Naive Bayes", "SVM linear"]:
        model = pipeline(kind).fit([s["text"] for s in groups["train"]], [s[task] for s in groups["train"]])
        score = macro_f1([s[task] for s in groups["validation"]], model.predict([s["text"] for s in groups["validation"]]), labels)
        if best is None or score > best[0]:
            best = (score, kind, model)
    _, kind, model = best
    order = [list(model.classes_).index(label) for label in labels]

    def proba(samples):
        texts = [s["text"] for s in samples]
        if hasattr(model, "predict_proba"):
            values = model.predict_proba(texts)
        else:  # LinearSVC: softmax of the margins
            margins = model.decision_function(texts)
            values = np.exp(margins - margins.max(axis=1, keepdims=True))
            values /= values.sum(axis=1, keepdims=True)
        return values[:, order]
    return kind, proba(groups["validation"]), proba(groups["test"])


def pick(scores):
    """Best validation score; ties go to the parameter closest to an even mix."""
    return max(scores, key=lambda item: (round(item[1], 6), -abs(item[0] - 0.5) if isinstance(item[0], float) else 0))


def evaluate(task, tf_val, tf_test, qv_val, qv_test, y_val, y_test, val_groups):
    labels = LABELS[task]
    names = np.array(labels)
    score = lambda y, probs: macro_f1(y, names[probs.argmax(axis=1)], labels)
    methods = {}

    methods["TF-IDF sozinho"] = {"param": None, "val": score(y_val, tf_val), "test_pred": names[tf_test.argmax(axis=1)]}
    methods["Qev sozinho"] = {"param": None, "val": score(y_val, qv_val), "test_pred": names[qv_test.argmax(axis=1)]}

    for name, combine in (("Média ponderada", lambda a, t, q: a * t + (1 - a) * q),
                          ("Log-linear", lambda a, t, q: a * np.log(t + EPS) + (1 - a) * np.log(q + EPS))):
        alpha, val = pick([(a, score(y_val, combine(a, tf_val, qv_val))) for a in ALPHAS])
        methods[name] = {"param": f"peso TF-IDF = {alpha}", "val": val,
                         "test_pred": names[combine(alpha, tf_test, qv_test).argmax(axis=1)]}

    features = lambda t, q: np.hstack([np.log(t + EPS), np.log(q + EPS)])
    stack = lambda: LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000)
    out_of_fold = np.empty(len(y_val), dtype=object)
    for fit_idx, held_idx in GroupKFold(n_splits=5).split(tf_val, y_val, val_groups):
        model = stack().fit(features(tf_val[fit_idx], qv_val[fit_idx]), np.array(y_val)[fit_idx])
        out_of_fold[held_idx] = model.predict(features(tf_val[held_idx], qv_val[held_idx]))
    final = stack().fit(features(tf_val, qv_val), y_val)
    methods["Stacking (validação cruzada por grupo)"] = {
        "param": "regressão logística sobre as log-probabilidades", "val": macro_f1(y_val, out_of_fold, labels),
        "test_pred": final.predict(features(tf_test, qv_test))}

    if task == "priority":
        urgent = labels.index("urgente")

        def override(t, tf_p, qv_p):
            predicted = names[tf_p.argmax(axis=1)].copy()
            predicted[qv_p[:, urgent] >= t] = "urgente"
            return predicted
        threshold, val = pick([(t, macro_f1(y_val, override(t, tf_val, qv_val), labels))
                               for t in [round(x, 2) for x in np.arange(0.3, 0.951, 0.05)]])
        methods["TF-IDF + alerta de urgência do Qev"] = {"param": f"P(urgente) Qev ≥ {threshold}", "val": val,
                                                         "test_pred": override(threshold, tf_test, qv_test)}

    chosen = max(methods, key=lambda name: round(methods[name]["val"], 6))
    rows = {}
    for name, method in methods.items():
        pred = method["test_pred"]
        cm = confusion_matrix(y_test, pred, labels=labels)
        rows[name] = {"param": method["param"], "validation_macro_f1": round(method["val"], 4),
                      "test_macro_f1": round(macro_f1(y_test, pred, labels), 4),
                      "test_recall": {label: round(float(cm[i, i] / max(cm[i].sum(), 1)), 3) for i, label in enumerate(labels)},
                      "test_confusion": cm.tolist()}
    return chosen, rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qev-probs", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    qev = json.loads(Path(args.qev_probs).read_text())
    if qev["corpus_version"] != CORPUS_VERSION:
        raise SystemExit(f"Qev probabilities are for corpus v{qev['corpus_version']}, project is v{CORPUS_VERSION}")
    samples = bootstrap_samples()
    groups = {name: [s for s in samples if partition(s["group_id"]) == name] for name in ("train", "validation", "test")}

    report = {"corpus_version": CORPUS_VERSION, "qev": "twainsk/qev-0.8b zero-shot, pt", "tasks": {}}
    for task in LABELS:
        kind, tf_val, tf_test = tfidf_probabilities(task, groups)
        qv_val = np.array([qev["probabilities"][s["id"]][task] for s in groups["validation"]])
        qv_test = np.array([qev["probabilities"][s["id"]][task] for s in groups["test"]])
        y_val = [s[task] for s in groups["validation"]]
        y_test = [s[task] for s in groups["test"]]
        chosen, rows = evaluate(task, tf_val, tf_test, qv_val, qv_test, y_val, y_test,
                                [s["group_id"] for s in groups["validation"]])
        report["tasks"][task] = {"tfidf_model": kind, "chosen_on_validation": chosen, "methods": rows}

        print(f"\n=== {task} (TF-IDF: {kind}) ===")
        print(f"{'método':42s} {'val F1':>7s} {'teste F1':>8s}  recall no teste")
        for name, row in rows.items():
            mark = "  <- escolhido na validação" if name == chosen else ""
            recall = " ".join(f"{k[:4]}={v:.2f}" for k, v in row["test_recall"].items())
            print(f"{name:42s} {row['validation_macro_f1']:7.3f} {row['test_macro_f1']:8.3f}  {recall}{mark}")
            if row["param"]:
                print(f"{'':44s}({row['param']})")
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
