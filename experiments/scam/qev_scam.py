"""Qev 0.8B zero-shot como detector de golpe. Resultado: não serve (ver docs/AVALIACAO.md).

1. Pergunta sim/não em português, fixada antes: avaliada em EVAL.
2. Como falhou, quatro formatos comparados em DEV; o melhor de DEV avaliado uma vez em EVAL.
Com o Foco aberto (Qev em 127.0.0.1:11436):  .venv/bin/python experiments/scam/qev_scam.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("FOCO_DATA_DIR", tempfile.mkdtemp(prefix="foco-scam-"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import httpx  # noqa: E402
from backend import qev  # noqa: E402
from emails import DEV, EVAL, report  # noqa: E402

SIGNS_PT = ("pede senha, código de verificação ou dados bancários; ameaça bloquear a conta; cobra taxa ou pagamento "
            "inesperado; promete prêmio; se passa por banco, empresa ou conhecido")
SIGNS_EN = ("asks for a password, verification code or bank details; threatens to block an account; demands an unexpected "
            "fee or payment; promises a prize; impersonates a bank, company or acquaintance")
VARIANTS = {
    "sim/não pt": {"type": "noul", "instructions": f"Este e-mail parece golpe ou phishing? Sinais típicos: {SIGNS_PT}.",
                   "criteria": {"false": "Mensagem legítima, mesmo que fale de senha, pagamento ou banco.", "true": "Golpe ou tentativa de phishing."}},
    "sim/não en": {"type": "noul", "instructions": f"Is this email a scam or phishing attempt? Typical signs: {SIGNS_EN}.",
                   "criteria": {"false": "Legitimate message, even if it mentions passwords, payments or banks.", "true": "Scam or phishing attempt."}},
    "escolha pt": {"type": "choice", "instructions": "Este e-mail é golpe ou legítimo?",
                   "criteria": {"golpe": f"Golpe ou phishing: {SIGNS_PT}.",
                                "legitimo": "Legítimo: mensagem real de uma pessoa ou empresa, mesmo que fale de senha, pagamento ou banco."}},
    "escolha en": {"type": "choice", "instructions": "Is this email a scam or legitimate?",
                   "criteria": {"golpe": f"Scam or phishing: {SIGNS_EN}.",
                                "legitimo": "Legitimate: a real message from a person or company, even if it mentions passwords, payments or banks."}},
}
PREREGISTERED = "sim/não pt"


def ask(text, question):
    response = httpx.post(qev.base_url() + "/v1/systemone", timeout=120, trust_env=False,
                          json={"model": "qev-0.8b", "state": text, "questions": {"scam": question}})
    response.raise_for_status()
    return response.json()["answers"]["scam"]


def scores(question, emails):
    values = []
    for _, subject, body in emails:
        answer = ask(f"{subject}\n{body}", question)
        values.append(answer["noul"] if question["type"] == "noul" else answer["probabilities"]["golpe"])
    return values


def main():
    if not qev.online():
        raise SystemExit("Qev não está respondendo. Abra o Foco com o Qev instalado.")
    print("== Pergunta fixada antes, na avaliação")
    report(PREREGISTERED, scores(VARIANTS[PREREGISTERED], EVAL), EVAL)
    print("\n== Formatos no desenvolvimento")
    dev = {}
    for name, question in VARIANTS.items():
        values = scores(question, DEV)
        dev[name] = sum((s >= .5) == t for s, (t, _, _) in zip(values, DEV))
        report(name, values, DEV)
    best = max(dev, key=dev.get)
    print(f"\n== Melhor no desenvolvimento ({best}), na avaliação")
    report(best, scores(VARIANTS[best], EVAL), EVAL)


if __name__ == "__main__":
    main()
