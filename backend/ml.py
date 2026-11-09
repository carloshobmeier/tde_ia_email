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
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC
from . import qev
from .config import MODEL_PATH, CATEGORIES, PRIORITIES
from .corpus import CORPUS_VERSION, bootstrap_samples, partition
from .db import connect, rows, now, set_setting

_model = None
_lock = threading.RLock()
LABELS = {"category": CATEGORIES, "priority": PRIORITIES}
# Só para exibir indícios (sem acentos, como o TF-IDF); o modelo continua usando todos os termos.
FUNCTION_WORDS = set("a o as os e de da do das dos em no na nos nas um uma uns umas que para por com se foi ao aos "
                     "e ja mais sua seu suas seus me te voce isso esta este essa esse ou mas nao sim".split())
QEV_NAME = "Qev (zero-shot)"
ENSEMBLE_NAME = "TF-IDF + Qev"
COMBINATIONS = {"media": "média ponderada", "log-linear": "log-linear"}
ALPHAS = [i / 20 for i in range(1, 20)]  # peso do TF-IDF; 0 e 1 são os modelos isolados
EPS = 1e-6


def pipeline(kind):
    classifiers = {
        "Regressão logística": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
        "Naive Bayes": MultinomialNB(alpha=0.5),
        "SVM linear": LinearSVC(class_weight="balanced", random_state=42),
        "Classe majoritária": DummyClassifier(strategy="most_frequent"),
    }
    # Palavras/bigramas explicam a decisão; n-gramas de caracteres toleram flexões
    # e erros de digitação ("disciplina"/"disciplinas", "urgente"/"urgência").
    features = FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode", sublinear_tf=True, max_features=18000)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), strip_accents="unicode", sublinear_tf=True, max_features=40000)),
    ])
    return Pipeline([("tfidf", features), ("clf", classifiers[kind])])


def input_text(subject, body):
    return f"{subject}\n{body[:24000]}"


def probabilities(pipe, texts, labels):
    """Matriz [textos x labels]. SVM linear não tem probabilidades: softmax das margens."""
    clf = pipe.named_steps["clf"]
    if hasattr(clf, "predict_proba"):
        values = pipe.predict_proba(texts)
    else:
        margins = np.atleast_2d(pipe.decision_function(texts))
        values = np.exp(margins - margins.max(axis=1, keepdims=True))
        values /= values.sum(axis=1, keepdims=True)
    classes = list(clf.classes_)
    result = np.zeros((len(texts), len(labels)))
    for column, label in enumerate(labels):
        if label in classes:
            result[:, column] = values[:, classes.index(label)]
    return result


def combine(params, tfidf, qev_probs):
    """Combina as probabilidades dos dois modelos; `alpha` é o peso do TF-IDF."""
    method, alpha = params["method"], params.get("alpha")
    if method == "tfidf":
        return tfidf
    if method == "qev":
        return qev_probs
    if method == "media":
        return alpha * tfidf + (1 - alpha) * qev_probs
    if method == "log-linear":
        z = alpha * np.log(tfidf + EPS) + (1 - alpha) * np.log(qev_probs + EPS)
        z = np.exp(z - z.max(axis=1, keepdims=True))
        return z / z.sum(axis=1, keepdims=True)
    raise ValueError(f"Combinação desconhecida: {method}")


def select_combination(labels, tfidf_val, qev_val, y_val):
    """Escolhe na validação: TF-IDF, Qev, média ponderada ou log-linear (com o melhor peso).

    Empates de peso ficam com o mais próximo de 0,5; empates de método, com o mais simples.
    Retorna (escolhido, candidatos), cada um como (parâmetros, macro-F1 na validação).
    """
    names = np.array(labels)
    score = lambda probs: float(f1_score(y_val, names[probs.argmax(axis=1)], labels=labels, average="macro", zero_division=0))
    candidates = [({"method": "tfidf"}, score(tfidf_val)), ({"method": "qev"}, score(qev_val))]
    for method in COMBINATIONS:
        scored = [({"method": method, "alpha": alpha}, score(combine({"method": method, "alpha": alpha}, tfidf_val, qev_val)))
                  for alpha in ALPHAS]
        candidates.append(max(scored, key=lambda c: (round(c[1], 6), -abs(c[0]["alpha"] - 0.5))))
    chosen = max(candidates, key=lambda c: round(c[1], 6))
    return chosen, candidates


def evaluation_samples():
    return [s for s in rows("SELECT text,group_id FROM samples") if partition(s["group_id"]) != "train"]


def qev_evaluation_status(samples=None):
    """Quantos exemplos de validação/teste já têm resposta do Qev em cache."""
    samples = evaluation_samples() if samples is None else samples
    keys = {qev.text_key(s["text"]) for s in samples}
    return {"installed": qev.installed(), "cached": len(qev.cached(keys)), "total": len(keys)}


def train():
    global _model
    with _lock:
        with connect() as db:
            # O corpus sintético é sempre o da versão atual; dados importados permanecem.
            db.execute("DELETE FROM samples WHERE source='synthetic'")
            db.executemany("INSERT OR IGNORE INTO samples VALUES (:id,:text,:category,:priority,:group_id,:source)", bootstrap_samples())
        samples = rows("SELECT * FROM samples")
        # Correções nunca alteram exemplos dos conjuntos congelados de avaliação.
        feedback = rows("SELECT text,category,priority,group_id FROM feedback")
        known_texts = {hashlib.sha256(s["text"].strip().lower().encode()).hexdigest() for s in samples}
        train_feedback = [s for s in feedback if partition(s["group_id"]) == "train"
                          and hashlib.sha256(s["text"].strip().lower().encode()).hexdigest() not in known_texts]
        groups = {part: [s for s in samples if partition(s["group_id"]) == part]
                  for part in ["train", "validation", "test"]}
        groups["train"].extend(train_feedback)
        # Qev entra só com resposta em cache para toda a validação e todo o teste.
        status = qev_evaluation_status(groups["validation"] + groups["test"])
        qev_ready = status["installed"] and status["total"] > 0 and status["cached"] == status["total"]
        qev_probs = qev.cached(qev.text_key(s["text"]) for s in groups["validation"] + groups["test"]) if qev_ready else {}
        fitted, reports, tfidf_reports, comparisons, ensemble = {}, {}, {}, [], {}
        for target, labels in LABELS.items():
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
            tfidf_test = probabilities(model, [s["text"] for s in groups["test"]], labels)
            y_pred = np.array(labels)[tfidf_test.argmax(axis=1)]
            tfidf_reports[target] = {"model": kind, "labels": labels,
                                     "report": classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0),
                                     "confusion": confusion_matrix(y_true, y_pred, labels=labels).tolist()}
            reports[target] = tfidf_reports[target]
            if qev_ready:
                matrix = lambda part: np.array([qev_probs[qev.text_key(s["text"])][target] for s in groups[part]])
                tfidf_val = probabilities(model, [s["text"] for s in groups["validation"]], labels)
                (params, _), options = select_combination(labels, tfidf_val, matrix("validation"), [s[target] for s in groups["validation"]])
                comparisons.append({"task": target, "model": QEV_NAME, "validation_f1": round(options[1][1], 4)})
                best_mix = max(options[2:], key=lambda c: round(c[1], 6))
                comparisons.append({"task": target, "model": ENSEMBLE_NAME, "validation_f1": round(best_mix[1], 4)})
                ensemble[target] = params
                if params["method"] != "tfidf":
                    y_pred = np.array(labels)[combine(params, tfidf_test, matrix("test")).argmax(axis=1)]
                    name = QEV_NAME if params["method"] == "qev" else ENSEMBLE_NAME
                    reports[target] = {"model": name, "labels": labels, "combination": {**params, "tfidf_model": kind},
                                       "report": classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0),
                                       "confusion": confusion_matrix(y_true, y_pred, labels=labels).tolist()}
        report = {"trained_at": now(), "synthetic": sum(s["source"] == "synthetic" for s in samples),
                  "imported": sum(s["source"] != "synthetic" for s in samples),
                  "feedback_used": len(train_feedback), "splits": {p: len(g) for p, g in groups.items()},
                  "distribution": dict(Counter(s["category"] for s in samples)),
                  "results": reports, "results_tfidf": tfidf_reports, "comparisons": comparisons,
                  "qev": {**status, "used": bool(ensemble)},
                  "evaluation_scope": "synthetic" if all(s["source"] == "synthetic" for s in samples) else "mixed",
                  "note": "Partições fixas por grupo. Seleção na validação; métricas finais no teste. No corpus sintético, "
                          "validação e teste usam frases que o treino nunca viu. Não comprova desempenho em e-mails reais."}
        fitted["version"] = report["trained_at"]
        fitted["corpus"] = CORPUS_VERSION
        if ensemble:
            fitted.update(ensemble=ensemble, ensemble_samples=status["total"], qev_cache_model=qev.cache_model())
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


def is_current():
    """Falso se o modelo salvo foi treinado com outra versão do corpus sintético."""
    return get_model().get("corpus") == CORPUS_VERSION


def classify(subject, body):
    """TF-IDF sempre; combinado ao Qev quando há resposta dele em cache para este texto."""
    models = get_model()
    text = input_text(subject, body)
    final = {task: probabilities(models[task], [text], labels)[0] for task, labels in LABELS.items()}
    ensemble, answer = models.get("ensemble"), None
    if ensemble and models.get("qev_cache_model") == qev.cache_model():
        key = qev.text_key(text)
        answer = qev.cached([key]).get(key)
    if answer:
        final = {task: combine(ensemble[task], final[task][None], np.array(answer[task])[None])[0] for task in LABELS}
    category = CATEGORIES[int(final["category"].argmax())]
    priority = PRIORITIES[int(final["priority"].argmax())]
    return {"category": category, "priority": priority, "confidence": float(final["priority"].max()),
            "signals": json.dumps(signals(models["priority"], text, priority)),
            "classifier": ENSEMBLE_NAME if answer else "TF-IDF"}


def signals(pipe, text, label):
    """Palavras do TF-IDF que mais pesam a favor da prioridade final."""
    clf = pipe.named_steps["clf"]
    if label not in clf.classes_:
        return []
    weights = class_weights(clf, label)
    if weights is None:
        return []
    values = pipe.named_steps["tfidf"].transform([text]).toarray()[0] * weights
    names = pipe.named_steps["tfidf"].get_feature_names_out()
    # Só palavras são mostradas como indício: fragmentos de caracteres não explicam nada ao usuário.
    ranked = [str(names[i]).removeprefix("word__") for i in np.argsort(values)[::-1]
              if values[i] > 0 and not names[i].startswith("char__")]
    return [name for name in ranked if not set(name.split()) <= FUNCTION_WORDS][:4]


def class_weights(clf, label):
    """Peso de cada termo a favor de `label`: coeficiente linear, ou no Naive Bayes
    a log-probabilidade do termo na classe menos a média nas demais classes."""
    index = list(clf.classes_).index(label)
    if hasattr(clf, "coef_"):
        return clf.coef_[index]
    if hasattr(clf, "feature_log_prob_"):
        log_prob = clf.feature_log_prob_
        return log_prob[index] - np.delete(log_prob, index, axis=0).mean(axis=0)
    return None
