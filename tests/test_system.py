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
from backend import db, llm, ml, providers
from backend.main import app, SESSION_TOKEN, serialize
from backend.mail import parse_eml, html_to_text, store_message
from backend.worker import enqueue, execute

EML = b"From: Ana <ana@example.com>\r\nTo: user@example.com\r\nSubject: Revisar proposta\r\nDate: Fri, 25 Sep 2026 10:00:00 -0300\r\nMessage-ID: <one@example.com>\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nPor favor revise a proposta hoje ate as 17h."


async def idle_worker(stop):
    await stop.wait()


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker_patch = patch("backend.main.run_worker", idle_worker)
        cls.worker_patch.start()
        cls.client = TestClient(app)
        cls.client.__enter__()
        cls.client.headers["X-Foco-Token"] = SESSION_TOKEN

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.worker_patch.stop()

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
        self.assertEqual(count, 12)
        self.client.post("/api/demo")
        self.assertEqual(self.client.get("/api/stats").json()["total"], count)
        self.assertEqual(len(self.client.get("/api/accounts").json()), 3)
        self.assertTrue(all(m["analysis_source"] == "demo" for m in self.client.get("/api/messages").json()["items"]))

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
        self.assertEqual(sum(report["splits"].values()), 180)
        self.assertEqual(len(report["comparisons"]), 8)
        self.assertEqual(ml.partition("same-thread"), ml.partition("same-thread"))
        examples = db.rows("SELECT group_id FROM samples")
        partitions = {name: {s["group_id"] for s in examples if ml.partition(s["group_id"]) == name} for name in ['train', 'validation', 'test']}
        self.assertFalse(partitions['train'] & partitions['test'])
        self.assertFalse(partitions['validation'] & partitions['test'])

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
