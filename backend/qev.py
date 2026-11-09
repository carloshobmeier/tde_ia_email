"""Qev opcional: modelo de decisão local (twainsk/qev-0.8b) que o Foco combina ao TF-IDF.

O Qev escolhe entre opções fornecidas e devolve probabilidades, sem gerar texto. Roda num
servidor em loopback, iniciado por run.py com gravação de requisições desativada. Sem ele,
o Foco usa só o TF-IDF. As respostas ficam em cache por texto, então retreinar não repete o Qev.
"""
import hashlib
import json
import threading
from urllib.parse import urlparse
import httpx
from .config import CATEGORIES, PRIORITIES, QEV_MODEL_DIR, QEV_URL
from .db import connect, now

LABELS = {"category": CATEGORIES, "priority": PRIORITIES}
# Opções = definições do guia de anotação (docs/AVALIACAO.md). Redação em português,
# escolhida na validação do experimento em experiments/qev.
QUESTIONS = {
    "category": {"type": "choice", "instructions": "Qual é o propósito predominante deste e-mail?", "criteria": {
        "faculdade": "Faculdade: disciplinas, trabalhos acadêmicos, notas, matrícula, estágio obrigatório, biblioteca universitária.",
        "trabalho": "Trabalho: entregas profissionais, clientes, equipe, fornecedores e decisões de projeto na empresa.",
        "financeiro": "Financeiro: faturas, cobranças, boletos, extratos, recibos, pagamentos e reembolsos, inclusive mensalidade da faculdade.",
        "pessoal": "Pessoal: família, amigos, compromissos privados, saúde, viagens e serviços pessoais.",
        "promocoes": "Promoções: publicidade, ofertas, cupons e newsletters de lojas e marcas.",
    }},
    "priority": {"type": "choice", "instructions": "Qual é a prioridade deste e-mail para o destinatário, no momento em que foi recebido?", "criteria": {
        "urgente": "Urgente: exige uma ação explícita do destinatário em até 24 horas.",
        "normal": "Normal: pede ação ou retorno, mas sem urgência imediata.",
        "baixa": "Baixa: apenas informativo, sem ação pendente, assunto concluído ou propaganda não solicitada.",
    }},
}
# Avisa o refinador de que há mensagens novas, sem esperar a varredura periódica.
new_messages = threading.Event()


class QevError(Exception):
    pass


def base_url():
    parsed = urlparse(QEV_URL)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise QevError("O endereço do Qev deve ser local (loopback).")
    return QEV_URL.rstrip("/")


def installed():
    return (QEV_MODEL_DIR / "qev_config.json").is_file()


def cache_model():
    """Identidade das respostas em cache: pesos do modelo e redação das perguntas."""
    questions = hashlib.sha256(json.dumps(QUESTIONS, sort_keys=True).encode()).hexdigest()[:8]
    config = QEV_MODEL_DIR / "qev_config.json"
    weights = hashlib.sha256(config.read_bytes()).hexdigest()[:10] if config.is_file() else "externo"
    return f"qev-0.8b:{weights}:{questions}"


def text_key(text):
    return hashlib.sha256(text.encode()).hexdigest()


def online(timeout=1.0):
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.get(base_url() + "/health")
        return response.status_code == 200 and response.json().get("status") == "ok"
    except (httpx.HTTPError, QevError, ValueError):
        return False


def predict(text):
    """Probabilidades por tarefa, na ordem de LABELS."""
    try:
        with httpx.Client(timeout=httpx.Timeout(120, connect=3), trust_env=False) as client:
            response = client.post(base_url() + "/v1/systemone",
                                   json={"model": "qev-0.8b", "state": text, "questions": QUESTIONS})
        response.raise_for_status()
        answers = response.json()["answers"]
        result = {task: [float(answers[task]["probabilities"][label]) for label in labels]
                  for task, labels in LABELS.items()}
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise QevError("O Qev não respondeu como esperado.") from exc
    for values in result.values():
        if not all(0 <= value <= 1 for value in values) or abs(sum(values) - 1) > 1e-3:
            raise QevError("O Qev devolveu probabilidades inválidas.")
    return result


def cached(keys):
    """{chave: probabilidades} para as chaves já respondidas pelo modelo atual."""
    keys, model, found = list(keys), cache_model(), {}
    with connect() as db:
        for start in range(0, len(keys), 500):
            chunk = keys[start:start + 500]
            query = f"SELECT key,probs FROM qev_cache WHERE model=? AND key IN ({','.join('?' * len(chunk))})"
            found.update({row["key"]: json.loads(row["probs"]) for row in db.execute(query, (model, *chunk))})
    return found


def store(key, probabilities):
    with connect() as db:
        db.execute("INSERT OR REPLACE INTO qev_cache(key,model,probs,created_at) VALUES (?,?,?,?)",
                   (key, cache_model(), json.dumps(probabilities), now()))
