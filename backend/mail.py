import hashlib
import re
import uuid
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser
from .db import connect, now
from .ml import classify


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.hidden += 1
        elif tag in ("p", "br", "div", "li", "tr", "h1", "h2") and not self.hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self.hidden = max(0, self.hidden - 1)
        elif tag in ("p", "div", "li") and not self.hidden:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def html_to_text(html):
    parser = PlainHTML()
    parser.feed(html)
    return re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", "".join(parser.parts)).strip()


def parse_eml(raw):
    mail = BytesParser(policy=policy.default).parsebytes(raw)
    name, address = parseaddr(str(mail.get("From", "Remetente desconhecido")))
    part = mail.get_body(preferencelist=("plain", "html"))
    body = ""
    if part:
        try:
            content = part.get_content()
            body = html_to_text(content) if part.get_content_type() == "text/html" else content
        except (LookupError, UnicodeError):
            body = (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")
    try:
        received = parsedate_to_datetime(str(mail.get("Date", "")))
        if received.tzinfo is None:
            received = received.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        received = datetime.now(timezone.utc)
    # Hash do arquivo: uma reimportação é idempotente, mesmo com Message-ID ausente ou repetido.
    return {"remote_id": hashlib.sha256(raw).hexdigest(), "thread_id": str(mail.get("References", mail.get("Message-ID", ""))),
            "sender": name or address or "Remetente desconhecido", "sender_email": address,
            "subject": str(mail.get("Subject", "(sem assunto)")), "body": body[:200000],
            "received_at": received.astimezone(timezone.utc).isoformat(), "unread": 1}


def store_message(account_id, message):
    digest = hashlib.sha256((message["subject"] + message["body"]).encode()).hexdigest()
    with connect() as db:
        existing = db.execute("SELECT id,content_hash FROM messages WHERE account_id=? AND remote_id=?",
                              (account_id, message["remote_id"])).fetchone()
    if existing and existing["content_hash"] == digest:
        return existing["id"], False
    prediction = classify(message["subject"], message["body"])
    message_id = existing["id"] if existing else str(uuid.uuid4())
    values = {**message, **prediction, "id": message_id, "account_id": account_id,
              "content_hash": digest, "source_url": message.get("source_url"), "thread_id": message.get("thread_id", ""),
              "unread": int(message.get("unread", True))}
    with connect() as db:
        if existing:
            db.execute("""UPDATE messages SET subject=:subject,body=:body,content_hash=:content_hash,
                category=CASE WHEN corrected=0 THEN :category ELSE category END,
                priority=CASE WHEN corrected=0 THEN :priority ELSE priority END,
                confidence=:confidence,signals=:signals,
                analysis=NULL,analysis_source=NULL,draft=NULL,analyzed_at=NULL WHERE id=:id""", values)
        else:
            db.execute("""INSERT INTO messages(id,account_id,remote_id,thread_id,sender,sender_email,subject,body,
                received_at,category,priority,confidence,signals,unread,source_url,content_hash)
                VALUES (:id,:account_id,:remote_id,:thread_id,:sender,:sender_email,:subject,:body,
                :received_at,:category,:priority,:confidence,:signals,:unread,:source_url,:content_hash)""", values)
    return message_id, True
