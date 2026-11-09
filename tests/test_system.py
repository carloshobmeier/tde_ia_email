import asyncio
import base64
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Banco e modelos descartáveis; a suíte nunca usa a caixa pessoal.
_temp = tempfile.TemporaryDirectory(prefix="foco-tests-")
os.environ["FOCO_DATA_DIR"] = _temp.name

import httpx
from fastapi.testclient import TestClient
import numpy as np
from backend import corpus, db, llm, ml, providers, qev, refiner
from backend.main import app, SESSION_TOKEN, serialize
from backend.mail import parse_eml, html_to_text, store_message
from backend.worker import enqueue, execute
from scripts import runtime

EML = b"From: Ana <ana@example.com>\r\nTo: user@example.com\r\nSubject: Revisar proposta\r\nDate: Fri, 25 Sep 2026 10:00:00 -0300\r\nMessage-ID: <one@example.com>\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nPor favor revise a proposta hoje ate as 17h."


async def idle_worker(stop):
    await stop.wait()


def one_hot(labels, label, p=0.8):
    rest = (1 - p) / (len(labels) - 1)
    return [p if item == label else rest for item in labels]


TRUTH = {s["text"]: s for s in corpus.bootstrap_samples()}


def fake_qev(text):
    """Qev imperfeito e determinístico: acerta ~2/3 do corpus; mensagens reais viram financeiro/baixa."""
    sample = TRUTH.get(text)
    if sample is None:
        return {"category": one_hot(ml.CATEGORIES, "financeiro"), "priority": one_hot(ml.PRIORITIES, "baixa")}
    right = int(hashlib.sha256(text.encode()).hexdigest(), 16) % 3 != 0
    return {"category": one_hot(ml.CATEGORIES, sample["category"] if right else "promocoes"),
            "priority": one_hot(ml.PRIORITIES, sample["priority"] if right else "normal")}


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker_patch = patch("backend.main.run_worker", idle_worker)
        cls.worker_patch.start()
        cls.refiner_patch = patch("backend.main.run_refiner", idle_worker)
        cls.refiner_patch.start()
        cls.client = TestClient(app)
        cls.client.__enter__()
        cls.client.headers["X-Foco-Token"] = SESSION_TOKEN

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.worker_patch.stop()
        cls.refiner_patch.stop()

    def setUp(self):
        with db.connect() as conn:
            conn.execute("DELETE FROM jobs")
            conn.execute("DELETE FROM accounts")

    def import_one(self):
        response = self.client.post("/api/import/eml", files=[("files", ("mail.eml", EML, "message/rfc822"))])
        self.assertEqual(response.status_code, 200, response.text)
        return self.client.get("/api/messages").json()["items"][0]

    def test_security_requires_session_for_mutations(self):
        response = self.client.post("/api/demo", headers={"X-Foco-Token": ""})
        self.assertEqual(response.status_code, 403)
        response = self.client.post("/api/demo", headers={"Origin": "https://attacker.example"})
        self.assertEqual(response.status_code, 403)

    def test_security_rejects_dns_rebinding_and_cross_site_reads(self):
        self.assertEqual(self.client.get("/api/bootstrap", headers={"Host": "attacker.example"}).status_code, 403)
        self.assertEqual(self.client.get("/api/bootstrap", headers={"Sec-Fetch-Site": "cross-site"}).status_code, 403)
        self.assertIn("frame-ancestors 'none'", self.client.get("/api/bootstrap").headers["Content-Security-Policy"])

    def test_demo_is_explicit_and_repeatable(self):
        self.assertEqual(self.client.get("/api/stats").json()["total"], 0)
        self.assertEqual(self.client.post("/api/demo").status_code, 200)
        count = self.client.get("/api/stats").json()["total"]
        self.assertEqual(count, 24)
        self.client.post("/api/demo")
        self.assertEqual(self.client.get("/api/stats").json()["total"], count)
        self.assertEqual(len(self.client.get("/api/accounts").json()), 3)
        messages = db.rows("SELECT editorial,analysis_source,remote_id FROM messages")
        editorial = [m for m in messages if m["editorial"]]
        live = [m for m in messages if not m["editorial"]]
        self.assertEqual((len(editorial), len(live)), (18, 6))
        self.assertTrue(all(m["analysis_source"] == "demo" for m in editorial))
        self.assertTrue(all(m["analysis_source"] is None and m["remote_id"].startswith("demo-live-") for m in live))

    def test_retraining_relabels_live_demo_but_never_editorial(self):
        self.client.post("/api/demo")
        with db.connect() as conn:
            conn.execute("UPDATE messages SET category='promocoes',priority='baixa'")  # rótulos "errados" de propósito
        job = enqueue("train", "classifier")
        asyncio.run(execute(db.rows("SELECT * FROM jobs WHERE id=?", (job["id"],))[0]))
        editorial = db.rows("SELECT category FROM messages WHERE editorial=1")
        live = db.rows("SELECT subject,category FROM messages WHERE editorial=0")
        self.assertTrue(all(m["category"] == "promocoes" for m in editorial), "editoriais nunca são reclassificados")
        self.assertNotEqual({m["category"] for m in live}, {"promocoes"}, "ao vivo são reclassificados pelos modelos")

    def test_import_idempotency_and_utf8(self):
        message = self.import_one()
        response = self.client.post("/api/import/eml", files=[("files", ("mail.eml", EML, "message/rfc822"))])
        self.assertEqual(response.json(), {"imported": 0, "duplicates": 1})
        detail = self.client.get("/api/messages/" + message["id"]).json()
        self.assertIn("revise", detail["body"])
        self.assertEqual(detail["received_at"], "2026-09-25T13:00:00+00:00")

    def test_import_validates_entire_batch_before_mutating(self):
        response = self.client.post("/api/import/eml", files=[("files", ("valid.eml", EML)), ("files", ("bad.exe", b"x"))])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/api/stats").json()["total"], 0)

    def test_feedback_saved_and_classification_corrected(self):
        message = self.import_one()
        result = self.client.patch("/api/messages/" + message["id"], json={"category": "faculdade", "priority": "urgente"})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["corrected"], 1)
        feedback = db.rows("SELECT * FROM feedback")
        self.assertEqual(len(feedback), 1)
        self.assertEqual(feedback[0]["category"], "faculdade")
        self.assertEqual(self.client.patch("/api/messages/" + message["id"], json={"priority": "inexistente"}).status_code, 422)

    def test_draft_star_status_and_snooze_are_persisted(self):
        message = self.import_one()
        until = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        response = self.client.patch("/api/messages/" + message["id"], json={"starred": True, "draft": "Vou verificar.", "snoozed_until": until})
        self.assertTrue(response.json()["snoozed"])
        self.assertEqual(self.client.get("/api/messages?view=snoozed").json()["total"], 1)
        self.assertEqual(self.client.get("/api/messages?view=today").json()["total"], 0)
        self.client.patch("/api/messages/" + message["id"], json={"clear_snooze": True, "status": "done"})
        result = self.client.get("/api/messages/" + message["id"]).json()
        self.assertEqual(result["draft"], "Vou verificar.")
        self.assertEqual(result["starred"], 1)
        self.assertEqual(self.client.get("/api/messages?view=done").json()["total"], 1)

    def test_search_escapes_wildcards_and_filters_accounts(self):
        message = self.import_one()
        self.assertEqual(self.client.get("/api/messages", params={"q": "proposta"}).json()["total"], 1)
        self.assertEqual(self.client.get("/api/messages", params={"q": "%"}).json()["total"], 0)
        self.assertEqual(self.client.get("/api/messages?account=nonexistent").json()["total"], 0)

    def test_removing_demo_preserves_imported_mail(self):
        message = self.import_one()
        self.client.post("/api/demo")
        self.assertEqual(self.client.delete("/api/demo").status_code, 200)
        self.assertEqual(self.client.get("/api/stats").json()["total"], 1)
        self.assertEqual(self.client.get("/api/messages/" + message["id"]).status_code, 200)

    def test_account_deletion_cascades_and_protects_running_jobs(self):
        message = self.import_one()
        self.client.patch("/api/messages/" + message["id"], json={"priority": "baixa"})
        job = enqueue("analyze", message["id"])
        with db.connect() as conn:
            conn.execute("UPDATE jobs SET status='running' WHERE id=?", (job["id"],))
        self.assertEqual(self.client.delete("/api/accounts/local-import").status_code, 409)
        with db.connect() as conn:
            conn.execute("UPDATE jobs SET status='done' WHERE id=?", (job["id"],))
        self.assertEqual(self.client.delete("/api/accounts/local-import").status_code, 200)
        self.assertEqual(len(db.rows("SELECT * FROM feedback")), 0)
        self.assertEqual(len(db.rows("SELECT * FROM jobs")), 0)

    def test_queue_deduplicates_and_recovers_interrupted_jobs(self):
        message = self.import_one()
        first = enqueue("analyze", message["id"])
        self.assertEqual(first, enqueue("analyze", message["id"]))
        with db.connect() as conn:
            conn.execute("UPDATE jobs SET status='running' WHERE id=?", (first["id"],))
        db.init_db()
        self.assertEqual(db.rows("SELECT status FROM jobs")[0]["status"], "queued")

    def test_ml_report_and_fixed_partitions(self):
        report = self.client.get("/api/ml/report").json()
        self.assertEqual(report["evaluation_scope"], "synthetic")
        self.assertEqual(sum(report["splits"].values()), len(corpus.bootstrap_samples()))
        self.assertEqual(len(report["comparisons"]), 8)
        self.assertEqual(ml.partition("same-thread"), ml.partition("same-thread"))
        examples = db.rows("SELECT group_id FROM samples")
        partitions = {name: {s["group_id"] for s in examples if ml.partition(s["group_id"]) == name} for name in ['train', 'validation', 'test']}
        self.assertFalse(partitions['train'] & partitions['test'])
        self.assertFalse(partitions['validation'] & partitions['test'])
        # Piso de regressão: bem acima da classe majoritária, sem exigir perfeição de um corpus sintético.
        for task in ("category", "priority"):
            self.assertGreater(report["results"][task]["report"]["macro avg"]["f1-score"], 0.7, task)

    def test_outdated_corpus_is_replaced(self):
        with db.connect() as conn:
            conn.execute("INSERT INTO samples VALUES ('old','texto antigo','trabalho','normal','bootstrap:old:0','synthetic')")
        with patch.object(ml, "_model", {"corpus": corpus.CORPUS_VERSION - 1}):
            self.assertFalse(ml.is_current())
        ml.train()
        self.assertTrue(ml.is_current())
        self.assertFalse(db.rows("SELECT id FROM samples WHERE id='old'"))

    def test_classification_explains_with_words(self):
        result = ml.classify("Prova antecipada", "A prova da disciplina foi antecipada para amanhã às 8h. Confirme hoje, é urgente.")
        signals = json.loads(result["signals"])
        self.assertEqual(result["priority"], "urgente")
        self.assertTrue(signals, "o indício da prioridade deve aparecer com qualquer modelo selecionado")
        self.assertFalse([s for s in signals if s.startswith(("char__", "word__"))])

    def test_qev_combination_end_to_end(self):
        other = EML.replace(b"Revisar proposta", b"Outra mensagem").replace(b"<one@", b"<two@")
        response = self.client.post("/api/import/eml", files=[("files", ("a.eml", EML)), ("files", ("b.eml", other))])
        self.assertEqual(response.json()["imported"], 2)
        items = {m["subject"]: m for m in self.client.get("/api/messages").json()["items"]}
        plain, corrected = items["Revisar proposta"], items["Outra mensagem"]
        self.client.patch("/api/messages/" + corrected["id"], json={"category": "pessoal", "priority": "urgente"})
        with patch.object(qev, "installed", return_value=True), patch.object(qev, "online", return_value=True), \
                patch.object(qev, "predict", side_effect=fake_qev):
            try:
                for _ in range(200):  # preenche a validação/teste em lotes até agendar o retreino
                    if refiner.step():
                        break
                status = self.client.get("/api/ml/report").json()["qev_live"]
                self.assertEqual(status["cached"], status["total"])
                job = db.rows("SELECT * FROM jobs WHERE kind='train' AND status='queued'")[0]
                asyncio.run(execute(job))
                report = self.client.get("/api/ml/report").json()
                self.assertTrue(report["qev"]["used"])
                self.assertTrue(report["qev_live"]["used"])
                for task in ("category", "priority"):
                    names = [c["model"] for c in report["comparisons"] if c["task"] == task]
                    self.assertIn(ml.QEV_NAME, names)
                    self.assertIn(ml.ENSEMBLE_NAME, names)
                    self.assertIn(report["results"][task]["model"], names, "o modelo selecionado precisa aparecer na comparação")
                # Combinação "só Qev" torna o efeito do refinador previsível.
                ml.get_model()["ensemble"] = {"category": {"method": "qev"}, "priority": {"method": "qev"}}
                qev.new_messages.set()
                refiner.step()
                refined = self.client.get("/api/messages/" + plain["id"]).json()
                self.assertEqual((refined["category"], refined["priority"]), ("financeiro", "baixa"))
                kept = self.client.get("/api/messages/" + corrected["id"]).json()
                self.assertEqual((kept["category"], kept["priority"]), ("pessoal", "urgente"))
                self.assertEqual(ml.classify(plain["subject"], refined["body"])["classifier"], ml.ENSEMBLE_NAME)
                self.assertEqual(ml.classify("Nunca visto", "Texto sem resposta do Qev.")["classifier"], "TF-IDF")
            finally:
                with db.connect() as conn:
                    conn.execute("DELETE FROM qev_cache")
                ml.train()
        self.assertFalse(ml.get_model().get("ensemble"))

    def test_bad_csv_is_atomic(self):
        before = len(db.rows("SELECT * FROM samples"))
        csv = b"text,category,priority,group_id\nvalid text,trabalho,normal,t1\nbad text,banana,normal,t2\n"
        response = self.client.post("/api/ml/import", files={"file": ("data.csv", csv)})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(db.rows("SELECT * FROM samples")), before)

    def test_confirmed_deadline_changes_priority(self):
        message = self.import_one()
        analysis = {"summary": "Prazo", "action": "Revisar", "due_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), "due_confirmed": False}
        with db.connect() as conn:
            conn.execute("UPDATE messages SET priority='baixa',analysis=? WHERE id=?", (json.dumps(analysis), message["id"]))
        self.assertEqual(self.client.get("/api/messages/" + message["id"]).json()["effective_priority"], "baixa")
        confirmed = self.client.patch("/api/messages/" + message["id"], json={"confirm_due": True}).json()
        self.assertEqual(confirmed["effective_priority"], "urgente")

    def test_cloud_models_rejected(self):
        self.assertEqual(self.client.put("/api/settings", json={"model": "example:cloud"}).status_code, 422)


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.samples = corpus.bootstrap_samples()
        self.by_split = {p: [s for s in self.samples if corpus.partition(s["group_id"]) == p] for p in ("train", "validation", "test")}

    def test_every_class_in_every_split(self):
        for split, samples in self.by_split.items():
            self.assertEqual({s["category"] for s in samples}, set(corpus.TOPICS), split)
            self.assertEqual({s["priority"] for s in samples}, {"urgente", "normal", "baixa"}, split)

    def test_evaluation_phrases_never_seen_in_training(self):
        # Sem isso, o teste mede memorização de templates (o problema da versão 1, com prioridade = 1,0).
        pools = [*corpus.CONTEXT.values(), *corpus.SENDERS.values(), corpus.NO_ACTION, *corpus.PROMO.values()]
        train_text = "\n".join(s["text"] for s in self.by_split["train"])
        held_out_text = "\n".join(s["text"] for s in self.by_split["validation"] + self.by_split["test"])
        for seen, held_out in pools:
            for phrase in held_out:
                self.assertFalse(phrase in train_text, f"frase de avaliação no treino: {phrase}")
            for phrase in seen:
                self.assertFalse(phrase in held_out_text, f"frase de treino na avaliação: {phrase}")

    def test_corpus_is_deterministic(self):
        self.assertEqual([s["id"] for s in self.samples], [s["id"] for s in corpus.bootstrap_samples()])


class QevTests(unittest.TestCase):
    LABELS = ["a", "b"]
    Y = ["a", "a", "b", "b"]
    TFIDF = np.array([[.9, .1], [.6, .4], [.6, .4], [.1, .9]])  # erra o terceiro
    QEV = np.array([[.4, .6], [.9, .1], [.1, .9], [.2, .8]])    # erra o primeiro

    def test_combination_chosen_when_it_beats_both_models(self):
        (params, score), candidates = ml.select_combination(self.LABELS, self.TFIDF, self.QEV, self.Y)
        self.assertIn(params["method"], ("media", "log-linear"))
        self.assertEqual(score, 1.0)
        self.assertLess(max(candidates[0][1], candidates[1][1]), 1.0)

    def test_simplest_model_wins_ties(self):
        perfect = np.array([[.9, .1], [.8, .2], [.2, .8], [.1, .9]])
        (params, _), _ = ml.select_combination(self.LABELS, perfect, self.QEV, self.Y)
        self.assertEqual(params, {"method": "tfidf"})

    def test_combinations_are_probabilities(self):
        for method in ("media", "log-linear"):
            combined = ml.combine({"method": method, "alpha": .3}, self.TFIDF, self.QEV)
            np.testing.assert_allclose(combined.sum(axis=1), 1.0)

    def test_qev_must_be_local(self):
        with patch.object(qev, "QEV_URL", "http://192.168.0.5:11436"):
            with self.assertRaises(qev.QevError):
                qev.base_url()
            self.assertFalse(qev.online())

    def test_qev_answers_are_validated(self):
        def server(probabilities):
            body = {"answers": {"category": {"probabilities": dict(zip(ml.CATEGORIES, probabilities["category"]))},
                                "priority": {"probabilities": dict(zip(ml.PRIORITIES, probabilities["priority"]))}}}
            transport, real_client = httpx.MockTransport(lambda request: httpx.Response(200, json=body)), httpx.Client
            return lambda **kwargs: real_client(transport=transport)
        good = {"category": [.1, .6, .1, .1, .1], "priority": [.2, .5, .3]}
        with patch.object(qev.httpx, "Client", server(good)):
            self.assertEqual(qev.predict("texto"), good)
        with patch.object(qev.httpx, "Client", server({**good, "priority": [.9, .9, .9]})):
            with self.assertRaises(qev.QevError):
                qev.predict("texto")

    def test_qev_server_never_records_requests(self):
        # Por padrão o `qev serve` grava cada requisição em disco; com e-mails, isso vazaria conteúdo.
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            python = base / "runtime" / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
            python.parent.mkdir(parents=True)
            python.touch()
            (base / "models" / "qev-0.8b").mkdir(parents=True)
            (base / "models" / "qev-0.8b" / "qev_config.json").write_text("{}")
            with patch.object(runtime, "QEV_DIR", base):
                command = runtime.qev_command()
        self.assertIn("--no-request-log", command)
        self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")


class ParsingAndAITests(unittest.TestCase):
    def test_wire_schema_avoids_unsupported_grammar_repetition(self):
        schema = llm.wire_schema(llm.Draft)
        self.assertNotIn("maxLength", json.dumps(schema))
        self.assertEqual(schema["properties"]["draft"]["type"], "string")

    def test_html_never_executes_and_strips_hidden_content(self):
        text = html_to_text('<head>Secret</head><p>Olá &amp; obrigado</p><script>steal()</script><img src="https://tracker.example"/><p>Fim</p>')
        self.assertEqual(text, "Olá & obrigado\n\nFim")
        self.assertNotIn("steal", text)

    def test_missing_date_and_bad_charset_are_tolerated(self):
        message = parse_eml(b"From: x@example.com\r\nSubject: Test\r\nContent-Type: text/plain; charset=invalid-charset\r\n\r\nHello")
        self.assertEqual(message["body"], "Hello")
        self.assertTrue(datetime.fromisoformat(message["received_at"]).tzinfo)

    def test_unsupported_deadline_removed(self):
        result = llm.Analysis(summary="Revisar", action="Revisar", due_at="2026-09-26T10:00:00-03:00", due_evidence="invented")
        message = {"subject": "Pedido", "body": "Sem data combinada."}
        with patch("backend.llm.generate", AsyncMock(return_value=result)):
            parsed = asyncio.run(llm.analyze(message))
        self.assertIsNone(parsed["due_at"])
        self.assertTrue(parsed["needs_review"])

    def test_supported_deadline_still_requires_confirmation(self):
        result = llm.Analysis(summary="Revisar", action="Revisar", due_at="2026-09-26T10:00:00-03:00", due_evidence="amanhã às 10h")
        with patch("backend.llm.generate", AsyncMock(return_value=result)):
            parsed = asyncio.run(llm.analyze({"subject": "Pedido", "body": "Envie amanhã às 10h."}))
        self.assertIsNotNone(parsed["due_at"])
        self.assertFalse(parsed["due_confirmed"])

    def analyze_with(self, result, message):
        with patch("backend.llm.generate", AsyncMock(return_value=result)):
            return asyncio.run(llm.analyze(message))

    def test_credential_request_never_becomes_an_action(self):
        result = llm.Analysis(summary="Pede a senha.", action="enviar a senha", due_at="2026-09-25T23:59:00-03:00",
                              due_evidence="responda com a sua senha")
        parsed = self.analyze_with(result, {"subject": "Conta", "body": "Para evitar o bloqueio, responda com a sua senha.",
                                            "received_at": "2026-09-25T10:00:00-03:00"})
        self.assertIsNone(parsed["action"])
        self.assertIsNone(parsed["due_at"])
        self.assertEqual(parsed["key_points"][0], llm.CREDENTIAL_WARNING)

    def test_null_written_as_text_is_no_action(self):
        # Caso real: action="null" (texto) manteria um "prazo" cuja evidência diz que não há prazo.
        result = llm.Analysis(summary="Informe.", action="null", due_at="2026-09-25T23:59:00-03:00",
                              due_evidence="não há prazo de entrega")
        parsed = self.analyze_with(result, {"subject": "Materiais", "body": "Nenhuma resposta e não há prazo de entrega.",
                                            "received_at": "2026-09-25T10:00:00-03:00"})
        self.assertIsNone(parsed["action"])
        self.assertIsNone(parsed["due_at"])

    def test_payment_with_barcode_is_not_flagged(self):
        result = llm.Analysis(summary="Boleto.", action="pagar o boleto com o código de barras")
        self.assertEqual(self.analyze_with(result, {"subject": "Boleto", "body": "Use o código de barras."})["action"],
                         "pagar o boleto com o código de barras")

    def test_implausible_deadline_year_dropped(self):
        result = llm.Analysis(summary="Revisar", action="Revisar", due_at="2100-09-26T17:00:00-03:00", due_evidence="amanhã às 17h")
        parsed = self.analyze_with(result, {"subject": "Pedido", "body": "Envie amanhã às 17h.",
                                            "received_at": "2026-09-25T10:00:00-03:00"})
        self.assertIsNone(parsed["due_at"])
        self.assertTrue(parsed["needs_review"])

    def test_promotion_creates_no_obligation(self):
        result = llm.Analysis(summary="Oferta.", action="aproveitar o desconto", due_at="2026-09-25T23:59:00-03:00",
                              due_evidence="até a meia-noite")
        parsed = self.analyze_with(result, {"subject": "Só hoje", "body": "Desconto até a meia-noite.",
                                            "category": "promocoes", "received_at": "2026-09-25T10:00:00-03:00"})
        self.assertIsNone(parsed["action"])
        self.assertIsNone(parsed["due_at"])

    def test_ollama_cannot_be_remote(self):
        with patch("backend.llm.OLLAMA_URL", "https://external.example"):
            with self.assertRaises(llm.AIError):
                llm.base_url()


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        db.init_db()
        with db.connect() as conn:
            conn.execute("DELETE FROM jobs")
            conn.execute("DELETE FROM accounts")
            conn.execute("INSERT INTO accounts(id,provider,email,name) VALUES ('test-gmail','gmail','test@example.com','Test')")

    async def test_gmail_pagination_cursor_and_dedup(self):
        calls = []
        def transport(request):
            calls.append(str(request.url))
            path = request.url.path
            if path.endswith('/profile'):
                return httpx.Response(200, json={"historyId": "99"})
            if path.endswith('/messages'):
                if request.url.params.get('pageToken') == 'next':
                    return httpx.Response(200, json={"messages": [{"id": "second"}]})
                return httpx.Response(200, json={"messages": [{"id": "first"}], "nextPageToken": "next"})
            return httpx.Response(200, json={"raw": base64.urlsafe_b64encode(EML).decode(), "labelIds": ["INBOX"], "threadId": "same-thread"})
        account = {"id": "test-gmail", "email": "test@example.com", "cursor": None}
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            cursor, count = await providers.sync_gmail(client, account, 30)
            _, again = await providers.sync_gmail(client, account, 30)
        self.assertEqual(cursor, "99")
        self.assertEqual(count, 2)
        self.assertEqual(again, 0)
        self.assertTrue(any('pageToken=next' in call for call in calls))

    async def test_gmail_expired_cursor_falls_back_to_full_sync(self):
        def transport(request):
            if request.url.path.endswith('/history'):
                return httpx.Response(404)
            if request.url.path.endswith('/profile'):
                return httpx.Response(200, json={"historyId": "new"})
            return httpx.Response(200, json={"messages": []})
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            cursor, count = await providers.sync_gmail(client, {"id": "test-gmail", "email": "test@example.com", "cursor": "expired"}, 30)
        self.assertEqual((cursor, count), ("new", 0))

    async def test_graph_rejects_foreign_pagination_link(self):
        def transport(request):
            return httpx.Response(200, json={"value": [], "@odata.nextLink": "https://attacker.example/steal"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            with self.assertRaises(providers.ProviderError):
                await providers.sync_outlook(client, {"id": "test-gmail", "cursor": None}, 30)

    async def test_graph_delta_pagination_and_cursor(self):
        calls = []
        def transport(request):
            calls.append(str(request.url))
            if request.url.params.get('page') == '2':
                return httpx.Response(200, json={"value": [], "@odata.deltaLink": "https://graph.microsoft.com/v1.0/delta?token=done"})
            return httpx.Response(200, json={"value": [{"id": "ms-one", "subject": "Reunião", "receivedDateTime": "2026-09-25T12:00:00Z", "from": {"emailAddress": {"name": "Marina", "address": "marina@example.com"}}, "body": {"contentType": "html", "content": "<p>Confira a proposta</p>"}}], "@odata.nextLink": "https://graph.microsoft.com/v1.0/next?page=2"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            cursor, count = await providers.sync_outlook(client, {"id": "test-gmail", "cursor": None}, 30)
        self.assertEqual(count, 1)
        self.assertIn('token=done', cursor)
        self.assertEqual(len(calls), 2)

    async def test_oauth_state_pkce_expiry(self):
        from urllib.parse import urlparse, parse_qs
        db.set_setting('preferences', {'gmail_client_id': 'test-client'})
        query = parse_qs(urlparse(providers.begin_auth('gmail')).query)
        self.assertEqual(query['code_challenge_method'], ['S256'])
        state = query['state'][0]
        providers.FLOWS[state]['expires'] = 0
        with self.assertRaises(providers.ProviderError):
            await providers.finish_auth('gmail', state, 'code')
        self.assertNotIn(state, providers.FLOWS)

    async def test_sync_errors_do_not_advance_cursor(self):
        with db.connect() as conn:
            conn.execute("UPDATE accounts SET cursor='old' WHERE id='test-gmail'")
        with patch('backend.providers.access_token', AsyncMock(side_effect=providers.ProviderError('Reconecte'))):
            with self.assertRaises(providers.ProviderError):
                await providers.synchronize('test-gmail')
        account = db.rows("SELECT * FROM accounts WHERE id='test-gmail'")[0]
        self.assertEqual(account['cursor'], 'old')
        self.assertEqual(account['error'], 'Reconecte')


if __name__ == '__main__':
    unittest.main()
