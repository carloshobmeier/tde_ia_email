"""Zero-shot Qev on the Foco corpus, with the same protocol as the TF-IDF models.

Qev is never trained on these emails. The answer options are the definitions from
docs/AVALIACAO.md (the annotation guide). The wording (pt/en) is chosen per task on
the validation split; only the selected wording's test score is the headline result.

Usage (inside the Qev runtime environment):
  python qev_email_eval.py --project <foco dir> --checkpoint <qev-0.8b dir> --out results.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

CRITERIA = {
    "pt": {
        "category": ("Qual é o propósito predominante deste e-mail?", {
            "faculdade": "Faculdade: disciplinas, trabalhos acadêmicos, notas, matrícula, estágio obrigatório, biblioteca universitária.",
            "trabalho": "Trabalho: entregas profissionais, clientes, equipe, fornecedores e decisões de projeto na empresa.",
            "financeiro": "Financeiro: faturas, cobranças, boletos, extratos, recibos, pagamentos e reembolsos, inclusive mensalidade da faculdade.",
            "pessoal": "Pessoal: família, amigos, compromissos privados, saúde, viagens e serviços pessoais.",
            "promocoes": "Promoções: publicidade, ofertas, cupons e newsletters de lojas e marcas.",
        }),
        "priority": ("Qual é a prioridade deste e-mail para o destinatário, no momento em que foi recebido?", {
            "urgente": "Urgente: exige uma ação explícita do destinatário em até 24 horas.",
            "normal": "Normal: pede ação ou retorno, mas sem urgência imediata.",
            "baixa": "Baixa: apenas informativo, sem ação pendente, assunto concluído ou propaganda não solicitada.",
        }),
    },
    "en": {
        "category": ("What is the main purpose of this email?", {
            "faculdade": "University: courses, assignments, grades, enrollment, internship reports, university library.",
            "trabalho": "Work: professional deliverables, clients, team, suppliers and project decisions at a company.",
            "financeiro": "Finance: invoices, bills, bank statements, receipts, payments and refunds, including tuition fees.",
            "pessoal": "Personal: family, friends, private appointments, health, travel and personal services.",
            "promocoes": "Promotions: advertising, offers, coupons and newsletters from stores and brands.",
        }),
        "priority": ("What is the priority of this email for the recipient at the moment it was received?", {
            "urgente": "Urgent: requires an explicit action from the recipient within 24 hours.",
            "normal": "Normal: asks for an action or reply, but not immediately urgent.",
            "baixa": "Low: informational only, no pending action, already resolved, or unsolicited advertising.",
        }),
    },
}
LABELS = {"category": ["faculdade", "trabalho", "financeiro", "pessoal", "promocoes"],
          "priority": ["urgente", "normal", "baixa"]}
# Same corpus (version 2) and splits, measured with backend.ml on 2026-11-09.
TFIDF_TEST = {"category": ("Regressão logística", 0.857), "priority": ("Naive Bayes", 0.794)}


def metrics(y_true, y_pred, labels):
    confusion = [[sum(t == a and p == b for t, p in zip(y_true, y_pred)) for b in labels] for a in labels]
    f1s = {}
    for i, label in enumerate(labels):
        tp = confusion[i][i]
        fp = sum(confusion[r][i] for r in range(len(labels))) - tp
        fn = sum(confusion[i]) - tp
        f1s[label] = 0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn)
    return {"macro_f1": sum(f1s.values()) / len(labels),
            "accuracy": sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true),
            "f1": f1s, "confusion": confusion}


def run(agent, samples, lang):
    questions = {task: {"type": "choice", "instructions": text, "criteria": options}
                 for task, (text, options) in CRITERIA[lang].items()}
    predictions = {task: [] for task in LABELS}
    started = time.perf_counter()
    for index, sample in enumerate(samples, 1):
        result = agent.predict(sample["text"], questions)
        for task in LABELS:
            predictions[task].append(result["answers"][task]["choice"])
        if index % 20 == 0:
            print(f"    {lang}: {index}/{len(samples)}", flush=True)
    seconds = time.perf_counter() - started
    report = {task: metrics([s[task] for s in samples], predictions[task], LABELS[task]) for task in LABELS}
    report["seconds_per_email"] = seconds / len(samples)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default=None, help="mps, cpu or cuda (default: automatic)")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(args.project).resolve()))
    from backend.corpus import CORPUS_VERSION, bootstrap_samples, partition
    from qev.inference import Agent

    samples = bootstrap_samples()
    splits = {name: [s for s in samples if partition(s["group_id"]) == name] for name in ("validation", "test")}
    print(f"Corpus v{CORPUS_VERSION}: validation={len(splits['validation'])} test={len(splits['test'])}", flush=True)
    print("Loading Qev (first run downloads Qwen3.5-0.8B, about 1.8 GB)...", flush=True)
    agent = Agent(args.checkpoint, backend="torch", device=args.device)
    print(f"Device: {agent.device}", flush=True)

    results = {}
    for split in ("validation", "test"):
        for lang in ("pt", "en"):
            print(f"  {split} / {lang}", flush=True)
            results[f"{split}_{lang}"] = run(agent, splits[split], lang)

    summary = {}
    for task in LABELS:
        chosen = max(("pt", "en"), key=lambda lang: results[f"validation_{lang}"][task]["macro_f1"])
        test = results[f"test_{chosen}"][task]
        summary[task] = {"wording_chosen_on_validation": chosen,
                         "validation_macro_f1": results[f"validation_{chosen}"][task]["macro_f1"],
                         "test_macro_f1": test["macro_f1"], "test_accuracy": test["accuracy"],
                         "test_f1_per_class": test["f1"], "test_confusion": test["confusion"],
                         "tfidf_test_macro_f1": TFIDF_TEST[task]}
    output = {"model": "twainsk/qev-0.8b (zero-shot)", "device": str(agent.device), "corpus_version": CORPUS_VERSION,
              "summary": summary, "all_runs": results}
    Path(args.out).write_text(json.dumps(output, ensure_ascii=False, indent=2))

    print("\n=== Test split (wording chosen on validation) ===")
    for task, row in summary.items():
        name, tfidf = row["tfidf_test_macro_f1"]
        print(f"{task:9s} Qev macro-F1 {row['test_macro_f1']:.3f} (acc {row['test_accuracy']:.3f}, {row['wording_chosen_on_validation']})"
              f"  vs  TF-IDF {name} {tfidf:.3f}")
        for label, line in zip(LABELS[task], row["test_confusion"]):
            print(f"    {label:10s} {line}")
    print(f"Seconds per email (2 questions): {results['test_pt']['seconds_per_email']:.2f}")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
