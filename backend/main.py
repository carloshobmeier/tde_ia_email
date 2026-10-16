import asyncio
import csv
import hashlib
import io
import json
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from .config import ROOT, PORT, ORIGIN, CATEGORIES, PRIORITIES, DEFAULT_MODEL
from .db import init_db, connect, rows, get_setting, set_setting, now
from . import ml, llm, providers
from .demo import seed_demo
from .mail import parse_eml, store_message
from .worker import enqueue, run_worker

SESSION_TOKEN = secrets.token_urlsafe(32)


@asynccontextmanager
async def lifespan(app):
    init_db()
    await asyncio.to_thread(ml.get_model)
    stop = asyncio.Event()
    worker = asyncio.create_task(run_worker(stop))
    yield
    stop.set()
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Foco local", version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def local_security(request: Request, call_next):
    host = request.url.hostname
    if host not in ("127.0.0.1", "localhost", "testserver"):
        return JSONResponse({"detail": "Acesso permitido apenas pelo endereço local."}, status_code=403)
    origin = request.headers.get("origin")
    allowed = {ORIGIN, f"http://localhost:{PORT}", "http://127.0.0.1:5173", "http://localhost:5173"}
    if origin and origin not in allowed:
        return JSONResponse({"detail": "Origem não permitida."}, status_code=403)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if not secrets.compare_digest(request.headers.get("x-foco-token", ""), SESSION_TOKEN):
            return JSONResponse({"detail": "Sessão local expirada. Atualize a página."}, status_code=403)
    # Impede páginas externas de lerem ou iniciarem operações no serviço local.
    if request.headers.get("sec-fetch-site") == "cross-site" and not request.url.path.startswith("/auth/"):
        return JSONResponse({"detail": "Requisição externa bloqueada."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith(("/api", "/auth")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(providers.ProviderError)
async def provider_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


def message_or_404(message_id):
    found = rows("SELECT m.*, a.email AS account_email,a.name AS account_name,a.color AS account_color,a.demo,a.provider FROM messages m JOIN accounts a ON a.id=m.account_id WHERE m.id=?", (message_id,))
    if not found:
        raise HTTPException(404, "Mensagem não encontrada.")
    return found[0]


def serialize(message, detail=False):
    item = dict(message)
    item["analysis"] = json.loads(item["analysis"]) if item.get("analysis") else None
    item["signals"] = json.loads(item.get("signals", "[]"))
    item["preview"] = " ".join(item["body"].split())[:180]
    item["effective_priority"] = item["priority"]
    item["overdue"] = False
    item["snoozed"] = bool(item.get("snoozed_until") and item["snoozed_until"] > now())
    due = (item["analysis"] or {}).get("due_at")
    # Datas não confirmadas aparecem como sugestões e não alteram a prioridade.
    if due and item["status"] != "done" and item["analysis"].get("due_confirmed"):
        try:
            delta = datetime.fromisoformat(due.replace("Z", "+00:00")) - datetime.now(timezone.utc)
            item["overdue"] = delta.total_seconds() < 0
            if delta <= timedelta(hours=24):
                item["effective_priority"] = "urgente"
        except (ValueError, TypeError):
            pass
    if not detail:
        item.pop("body", None)
        item.pop("draft", None)
    item.pop("content_hash", None)
    return item


@app.get("/api/bootstrap")
def bootstrap():
    return {"token": SESSION_TOKEN, "version": "1.0.0", "preferences": preferences(), "ml_ready": True}


@app.get("/api/accounts")
def accounts():
    return rows("""SELECT a.id,a.provider,a.email,a.name,a.color,a.last_sync,a.error,a.demo,
        COUNT(m.id) AS message_count FROM accounts a LEFT JOIN messages m ON m.account_id=a.id
        GROUP BY a.id ORDER BY a.demo DESC,a.name""")


@app.get("/api/messages")
def messages(account: str = "", q: str = "", category: str = "", view: str = "all", limit: int = 100, offset: int = 0):
    clauses, params = [], []
    if account:
        clauses.append("m.account_id=?")
        params.append(account)
    if category:
        clauses.append("m.category=?")
        params.append(category)
    if q.strip():
        clauses.append("(m.subject LIKE ? ESCAPE '\\' OR m.body LIKE ? ESCAPE '\\' OR m.sender LIKE ? ESCAPE '\\')")
        term = "%" + q[:200].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        params.extend([term] * 3)
    if view == "starred":
        clauses.append("m.starred=1")
    elif view == "done":
        clauses.append("m.status='done'")
    elif view == "snoozed":
        clauses.append("m.status!='done' AND julianday(m.snoozed_until)>julianday('now')")
    elif view == "actions":
        clauses.append("m.status!='done' AND COALESCE(julianday(m.snoozed_until),0)<=julianday('now') AND COALESCE(json_extract(m.analysis,'$.action'),'')!=''")
    elif view == "today":
        clauses.append("m.status!='done' AND COALESCE(julianday(m.snoozed_until),0)<=julianday('now')")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    total = rows("SELECT COUNT(*) AS n FROM messages m" + where, params)[0]["n"]
    order = "julianday(m.received_at) DESC"
    if view in ("today", "actions"):
        order = f"CASE WHEN {URGENT_SQL} THEN 0 WHEN m.priority='normal' THEN 1 ELSE 2 END, CASE WHEN COALESCE(json_extract(m.analysis,'$.action'),'')!='' THEN 0 ELSE 1 END," + order
    # A paginação acontece no SQLite; corpos inteiros e rascunhos só são lidos ao abrir a mensagem.
    fields = "m.id,m.account_id,m.remote_id,m.thread_id,m.sender,m.sender_email,m.subject,substr(m.body,1,220) AS body,m.received_at,m.category,m.priority,m.confidence,m.signals,m.unread,m.starred,m.status,m.snoozed_until,m.analysis,m.analysis_source,m.analyzed_at,m.source_url,m.corrected,a.email AS account_email,a.name AS account_name,a.color AS account_color,a.demo,a.provider"
    data = rows(f"SELECT {fields} FROM messages m JOIN accounts a ON a.id=m.account_id" + where + " ORDER BY " + order + " LIMIT ? OFFSET ?", [*params, min(max(limit, 1), 200), max(0, offset)])
    return {"items": [serialize(m) for m in data], "total": total}


URGENT_SQL = """(m.priority='urgente' OR (m.status!='done' AND json_extract(m.analysis,'$.due_confirmed')=1
    AND julianday(json_extract(m.analysis,'$.due_at'))<=julianday('now','+1 day')))"""


@app.get("/api/stats")
def stats():
    active = "m.status!='done' AND COALESCE(julianday(m.snoozed_until),0)<=julianday('now')"
    data = rows(f"""SELECT COUNT(*) AS total,
        COALESCE(SUM(({active}) AND {URGENT_SQL}),0) AS urgent,
        COALESCE(SUM(({active}) AND COALESCE(json_extract(m.analysis,'$.action'),'')!=''),0) AS actions,
        COALESCE(SUM(m.status='done'),0) AS done,COALESCE(SUM(m.unread),0) AS unread,
        COALESCE(SUM(m.analysis IS NULL),0) AS pending_analysis,COALESCE(SUM(a.demo),0) AS demo
        FROM messages m JOIN accounts a ON a.id=m.account_id""")[0]
    counts = {r['category']: r['n'] for r in rows("SELECT category,COUNT(*) AS n FROM messages GROUP BY category")}
    data['categories'] = {c: counts.get(c, 0) for c in CATEGORIES}
    return data


@app.get("/api/messages/{message_id}")
def message_detail(message_id: str):
    return serialize(message_or_404(message_id), True)


class MessageUpdate(BaseModel):
    unread: bool | None = None
    starred: bool | None = None
    status: Literal["pending", "done"] | None = None
    snoozed_until: datetime | None = None
    clear_snooze: bool = False
    category: Literal["faculdade", "trabalho", "financeiro", "pessoal", "promocoes"] | None = None
    priority: Literal["urgente", "normal", "baixa"] | None = None
    draft: str | None = Field(default=None, max_length=10000)
    confirm_due: bool | None = None


@app.patch("/api/messages/{message_id}")
def update_message(message_id: str, update: MessageUpdate):
    message = message_or_404(message_id)
    values = update.model_dump(exclude_none=True)
    clear_snooze = values.pop("clear_snooze", False)
    confirm = values.pop("confirm_due", None)
    if clear_snooze:
        values["snoozed_until"] = None
    elif update.snoozed_until:
        if not update.snoozed_until.tzinfo:
            raise HTTPException(400, "Informe um horário com fuso.")
        values["snoozed_until"] = update.snoozed_until.astimezone(timezone.utc).isoformat()
    if confirm is not None and message["analysis"]:
        analysis = json.loads(message["analysis"])
        if analysis.get("due_at"):
            analysis["due_confirmed"] = confirm
            values["analysis"] = json.dumps(analysis, ensure_ascii=False)
    with connect() as db:
        if update.category or update.priority:
            values["corrected"] = 1
            db.execute("INSERT OR REPLACE INTO feedback VALUES (?,?,?,?,?,?)", (
                message_id, message["subject"] + "\n" + message["body"], update.category or message["category"],
                update.priority or message["priority"], message["account_id"] + ":" + (message["thread_id"] or message["remote_id"]), now()))
        if values:
            # Chaves vêm exclusivamente do modelo validado acima.
            db.execute("UPDATE messages SET " + ",".join(f"{k}=?" for k in values) + " WHERE id=?", [*values.values(), message_id])
    return message_detail(message_id)


@app.post("/api/messages/{message_id}/analyze")
def analyze_message(message_id: str):
    message_or_404(message_id)
    return enqueue("analyze", message_id)


class DraftRequest(BaseModel):
    tone: Literal["cordial", "formal", "direto"] = "cordial"


@app.post("/api/messages/{message_id}/draft")
def draft_message(message_id: str, body: DraftRequest):
    message_or_404(message_id)
    return enqueue("draft:" + body.tone, message_id)


@app.post("/api/analyze-pending")
def analyze_pending():
    pending = rows("SELECT id FROM messages WHERE analysis IS NULL AND status!='done' ORDER BY CASE priority WHEN 'urgente' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,received_at DESC LIMIT 20")
    return {"jobs": [enqueue("analyze", row["id"]) for row in pending]}


@app.get("/api/jobs")
def jobs():
    return rows("SELECT id,kind,target,status,error,created_at,updated_at FROM jobs ORDER BY created_at DESC LIMIT 100")


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str):
    found = rows("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not found:
        raise HTTPException(404, "Tarefa não encontrada.")
    return enqueue(found[0]["kind"], found[0]["target"])


@app.post("/api/sync")
def sync_all():
    return {"jobs": [enqueue("sync", row["id"]) for row in rows("SELECT id FROM accounts WHERE demo=0 AND provider IN ('gmail','outlook')")]}


@app.post("/api/accounts/{account_id}/sync")
def sync_account(account_id: str):
    found = rows("SELECT id FROM accounts WHERE id=? AND demo=0 AND provider IN ('gmail','outlook')", (account_id,))
    if not found:
        raise HTTPException(400, "Esta conta não utiliza sincronização remota.")
    return enqueue("sync", account_id)


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: str):
    account = rows("SELECT * FROM accounts WHERE id=?", (account_id,))
    if not account:
        raise HTTPException(404, "Conta não encontrada.")
    if rows("SELECT id FROM jobs WHERE status='running' AND (target=? OR target IN (SELECT id FROM messages WHERE account_id=?))", (account_id, account_id)):
        raise HTTPException(409, "Aguarde a tarefa em andamento terminar antes de remover a conta.")
    if not account[0]["demo"] and account[0]["provider"] != "local":
        providers.vault_delete(account_id)
    with connect() as db:
        db.execute("DELETE FROM jobs WHERE target=? OR target IN (SELECT id FROM messages WHERE account_id=?)", (account_id, account_id))
        db.execute("DELETE FROM accounts WHERE id=?", (account_id,))
    return {"ok": True}


@app.post("/api/demo")
def create_demo():
    return seed_demo()


@app.delete("/api/demo")
def delete_demo():
    for account in rows("SELECT id FROM accounts WHERE demo=1"):
        delete_account(account["id"])
    return {"ok": True}


@app.post("/api/import/eml")
async def import_eml(files: list[UploadFile] = File(...)):
    if len(files) > 100:
        raise HTTPException(400, "Importe até 100 arquivos por vez.")
    prepared = []
    for file in files:
        if not (file.filename or "").lower().endswith(".eml"):
            raise HTTPException(400, "Selecione apenas arquivos .eml.")
        raw = await file.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            raise HTTPException(413, "Cada e-mail deve ter até 5 MB.")
        prepared.append(parse_eml(raw))
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO accounts(id,provider,email,name,color) VALUES ('local-import','local','arquivos@local','Importados','#b39363')")
    count = 0
    for message in prepared:
        _, created = await asyncio.to_thread(store_message, "local-import", message)
        count += int(created)
    return {"imported": count, "duplicates": len(prepared) - count}


class Preferences(BaseModel):
    display_name: str = Field(default="", max_length=60)
    model: str = Field(default=DEFAULT_MODEL, min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._:/-]+$")
    sync_days: int = Field(default=30, ge=1, le=365)
    gmail_client_id: str = Field(default="", max_length=250)
    outlook_client_id: str = Field(default="", max_length=250)

    @field_validator("model")
    @classmethod
    def local_model(cls, value):
        if "cloud" in value.lower():
            raise ValueError("Escolha um modelo local.")
        return value


def preferences():
    return Preferences(**get_setting("preferences", {})).model_dump()


@app.get("/api/settings")
def read_settings():
    return preferences()


@app.put("/api/settings")
def save_settings(body: Preferences):
    set_setting("preferences", body.model_dump())
    return preferences()


class Secret(BaseModel):
    value: str = Field(min_length=1, max_length=1000)


@app.put("/api/settings/gmail-secret")
def save_secret(body: Secret):
    providers.vault_set("gmail_client_secret", body.value)
    return {"ok": True}


@app.post("/api/auth/{provider}")
def authorize(provider: Literal["gmail", "outlook"]):
    return {"url": providers.begin_auth(provider)}


@app.get("/auth/{provider}/callback")
async def callback(provider: Literal["gmail", "outlook"], state: str = "", code: str = "", error: str = ""):
    if error or not code:
        providers.FLOWS.pop(state, None)
        return RedirectResponse("/?connection=cancelled")
    try:
        account_id = await providers.finish_auth(provider, state, code)
        enqueue("sync", account_id)
        return RedirectResponse("/?connection=success")
    except (providers.ProviderError, Exception):
        # Nenhum código OAuth ou token é refletido na página ou em logs de erro.
        return RedirectResponse("/?connection=failed")


@app.get("/api/ai/health")
async def ai_health():
    return await llm.health()


@app.get("/api/ml/report")
def ml_report():
    report = get_setting("ml_report", {})
    report["feedback_count"] = rows("SELECT COUNT(*) AS n FROM feedback")[0]["n"]
    return report


@app.post("/api/ml/train")
def train_model():
    return enqueue("train", "classifier")


@app.post("/api/ml/import")
async def import_dataset(file: UploadFile = File(...)):
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "O CSV deve ter até 5 MB.")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not {"text", "category", "priority", "group_id"}.issubset(reader.fieldnames or []):
            raise ValueError("Colunas obrigatórias: text,category,priority,group_id.")
        samples = []
        for index, sample in enumerate(reader, start=2):
            if sample["category"] not in CATEGORIES or sample["priority"] not in PRIORITIES or not sample["text"].strip() or not sample["group_id"].strip():
                raise ValueError(f"Rótulos, texto ou grupo inválidos na linha {index}.")
            if len(sample["text"]) > 100000:
                raise ValueError(f"Texto muito longo na linha {index}.")
            digest = hashlib.sha256(sample["text"].strip().lower().encode()).hexdigest()
            samples.append((digest, sample["text"], sample["category"], sample["priority"], "import:" + sample["group_id"], "imported"))
        if not samples:
            raise ValueError("O CSV está vazio.")
    except (UnicodeError, csv.Error, ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc
    with connect() as db:
        before = db.total_changes
        db.executemany("INSERT OR IGNORE INTO samples VALUES (?,?,?,?,?,?)", samples)
        count = db.total_changes - before
    return {"imported": count, "job": enqueue("train", "classifier")}


@app.get("/api/ml/export")
def export_feedback():
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["text", "category", "priority", "group_id"])
    for item in rows("SELECT text,category,priority,group_id FROM feedback"):
        # Evita execução de fórmulas ao abrir o arquivo em planilhas.
        writer.writerow([("'" + str(v)) if str(v).startswith(("=", "+", "-", "@")) else v for v in item.values()])
    return Response(stream.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="foco-correcoes.csv"'})


DIST = ROOT / "frontend" / "dist"
if (DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}")
def frontend(path: str):
    if path.startswith(("api/", "auth/")):
        raise HTTPException(404, "Rota não encontrada.")
    if path == "favicon.svg":
        return FileResponse(DIST / "favicon.svg")
    if (DIST / "index.html").exists():
        return FileResponse(DIST / "index.html")
    return JSONResponse({"message": "Foco está funcionando. Compile a interface com npm run build em frontend/."})
