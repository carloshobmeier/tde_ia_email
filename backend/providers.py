"""OAuth de aplicativo instalado; sincronização de leitura com cursores por conta."""
import asyncio
import base64
import hashlib
import json
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse
import httpx
import keyring
from .config import ORIGIN
from .db import connect, get_setting, now, rows
from .mail import parse_eml, html_to_text, store_message

FLOWS = {}
SERVICE = "foco-local"
SCOPES = {
    "gmail": "https://www.googleapis.com/auth/gmail.readonly",
    "outlook": "openid profile email offline_access User.Read Mail.Read",
}
TOKEN_URLS = {
    "gmail": "https://oauth2.googleapis.com/token",
    "outlook": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
}


class ProviderError(Exception):
    pass


def vault_get(key):
    try:
        value = keyring.get_password(SERVICE, key)
        return json.loads(value) if value else None
    except Exception as exc:
        raise ProviderError("O cofre de credenciais do sistema não está disponível.") from exc


def vault_set(key, value):
    try:
        keyring.set_password(SERVICE, key, json.dumps(value))
    except Exception as exc:
        raise ProviderError("Não foi possível salvar no cofre de credenciais do sistema. Nenhum token será salvo em texto puro.") from exc


def vault_delete(key):
    try:
        keyring.delete_password(SERVICE, key)
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception as exc:
        raise ProviderError("Não foi possível remover a credencial do cofre do sistema.") from exc


def begin_auth(provider):
    settings = get_setting("preferences", {})
    client_id = settings.get(f"{provider}_client_id", "").strip()
    if not client_id:
        raise ProviderError("Preencha o ID do aplicativo nas configurações antes de conectar a conta.")
    for key in list(FLOWS):
        if FLOWS[key]["expires"] < time.time():
            del FLOWS[key]
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    redirect = f"{ORIGIN}/auth/{provider}/callback"
    if provider == "outlook":
        redirect = redirect.replace("127.0.0.1", "localhost")
    FLOWS[state] = {"provider": provider, "verifier": verifier, "client_id": client_id,
                    "redirect": redirect, "expires": time.time() + 600}
    query = {"client_id": client_id, "redirect_uri": redirect, "response_type": "code",
             "scope": SCOPES[provider], "state": state, "code_challenge_method": "S256",
             "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()}
    if provider == "gmail":
        query.update(access_type="offline", prompt="consent")
        endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    else:
        query.update(prompt="select_account")
        endpoint = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    return endpoint + "?" + urlencode(query)


async def checked(response):
    if response.status_code in (401, 403):
        raise ProviderError("O provedor recusou o acesso. Reconecte a conta ou verifique as permissões do aplicativo.")
    if response.status_code == 429:
        raise ProviderError("O provedor limitou as solicitações. Aguarde alguns minutos e sincronize novamente.")
    if response.is_error:
        raise ProviderError(f"O provedor retornou erro {response.status_code}. Verifique a conexão e a configuração OAuth.")
    return response.json()


async def finish_auth(provider, state, code):
    flow = FLOWS.pop(state, None)
    if not flow or flow["expires"] < time.time() or flow["provider"] != provider:
        raise ProviderError("Autorização expirada ou inválida. Inicie a conexão novamente no Foco.")
    payload = {"client_id": flow["client_id"], "code": code, "code_verifier": flow["verifier"],
               "grant_type": "authorization_code", "redirect_uri": flow["redirect"]}
    if provider == "gmail":
        secret = vault_get("gmail_client_secret")
        if secret:
            payload["client_secret"] = secret
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        token = await checked(await client.post(TOKEN_URLS[provider], data=payload))
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        if provider == "gmail":
            profile = await checked(await client.get("https://gmail.googleapis.com/gmail/v1/users/me/profile", headers=headers))
            email, name = profile["emailAddress"], profile["emailAddress"].split("@")[0]
        else:
            profile = await checked(await client.get("https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName,displayName", headers=headers))
            email = profile.get("mail") or profile["userPrincipalName"]
            name = profile.get("displayName") or email.split("@")[0]
    existing = rows("SELECT id FROM accounts WHERE provider=? AND email=?", (provider, email))
    account_id = existing[0]["id"] if existing else str(uuid.uuid4())
    previous = vault_get(account_id) or {}
    token["refresh_token"] = token.get("refresh_token") or previous.get("refresh_token")
    token["expires_at"] = time.time() + token.get("expires_in", 3600) - 60
    token["client_id"] = flow["client_id"]
    vault_set(account_id, token)
    with connect() as db:
        db.execute("""INSERT INTO accounts(id,provider,email,name,color) VALUES (?,?,?,?,?)
            ON CONFLICT(provider,email) DO UPDATE SET error=NULL,name=excluded.name""",
                   (account_id, provider, email, name, "#d97c67" if provider == "gmail" else "#6c8bc5"))
    return account_id


async def access_token(account):
    token = vault_get(account["id"])
    if not token:
        raise ProviderError("Identificação indisponível. Reconecte esta conta.")
    if token.get("expires_at", 0) > time.time():
        return token["access_token"]
    if not token.get("refresh_token"):
        raise ProviderError("A sessão expirou. Reconecte esta conta.")
    provider = account["provider"]
    payload = {"client_id": token["client_id"], "refresh_token": token["refresh_token"], "grant_type": "refresh_token"}
    if provider == "gmail":
        secret = vault_get("gmail_client_secret")
        if secret:
            payload["client_secret"] = secret
    async with httpx.AsyncClient(timeout=30) as client:
        updated = await checked(await client.post(TOKEN_URLS[provider], data=payload))
    token.update(updated)
    token["expires_at"] = time.time() + updated.get("expires_in", 3600) - 60
    vault_set(account["id"], token)
    return token["access_token"]


def graph_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com" or not parsed.path.startswith("/v1.0/"):
        raise ProviderError("O provedor retornou um endereço de paginação inválido.")
    return url


async def sync_gmail(client, account, days):
    base = "https://gmail.googleapis.com/gmail/v1/users/me"
    ids, cursor = set(), account.get("cursor")
    if cursor:
        page, latest = None, cursor
        while True:
            params = {"startHistoryId": cursor, "maxResults": 100}
            if page:
                params["pageToken"] = page
            response = await client.get(base + "/history", params=params)
            if response.status_code == 404:
                cursor = None
                break
            data = await checked(response)
            for history in data.get("history", []):
                for item in history.get("messagesAdded", []):
                    ids.add(item["message"]["id"])
                for item in history.get("labelsAdded", []):
                    if "INBOX" in item.get("labelIds", []):
                        ids.add(item["message"]["id"])
            latest = data.get("historyId", latest)
            page = data.get("nextPageToken")
            if not page:
                break
    if not cursor:
        profile = await checked(await client.get(base + "/profile"))
        latest = profile["historyId"]
        page = None
        since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
        while True:
            params = {"q": f"in:inbox after:{since}", "maxResults": 100}
            if page:
                params["pageToken"] = page
            data = await checked(await client.get(base + "/messages", params=params))
            ids.update(item["id"] for item in data.get("messages", []))
            page = data.get("nextPageToken")
            if not page:
                break
    imported = 0
    for remote_id in sorted(ids):
        response = await client.get(f"{base}/messages/{remote_id}", params={"format": "raw"})
        if response.status_code == 404:
            continue
        data = await checked(response)
        if "INBOX" not in data.get("labelIds", []):
            continue
        raw = data["raw"]
        message = parse_eml(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        message.update(remote_id=remote_id, thread_id=data.get("threadId", remote_id),
                       unread="UNREAD" in data.get("labelIds", []),
                       source_url="https://mail.google.com/mail/u/" + account["email"] + "/#inbox/" + remote_id)
        _, created = await asyncio.to_thread(store_message, account["id"], message)
        imported += int(created)
    return str(latest), imported


async def sync_outlook(client, account, days):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    initial = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages/delta?" + urlencode({
        "$select": "id,conversationId,subject,from,body,receivedDateTime,isRead,webLink",
        "$filter": f"receivedDateTime ge {since}"})
    url, imported, reset = account.get("cursor") or initial, 0, False
    while url:
        response = await client.get(graph_url(url), headers={"Prefer": 'outlook.body-content-type="text", IdType="ImmutableId"'})
        if response.status_code == 410 and not reset:
            url, reset = initial, True
            continue
        data = await checked(response)
        for item in data.get("value", []):
            if "@removed" in item:
                continue  # Histórico local permanece disponível mesmo se removido no provedor.
            sender = (item.get("from") or {}).get("emailAddress", {})
            body = item.get("body", {})
            content = body.get("content", "")
            message = {"remote_id": item["id"], "thread_id": item.get("conversationId", item["id"]),
                       "sender": sender.get("name") or sender.get("address", "Desconhecido"),
                       "sender_email": sender.get("address", ""), "subject": item.get("subject") or "(sem assunto)",
                       "body": (html_to_text(content) if body.get("contentType", "").lower() == "html" else content)[:200000],
                       "received_at": item["receivedDateTime"], "unread": not item.get("isRead", False),
                       "source_url": item.get("webLink")}
            _, created = await asyncio.to_thread(store_message, account["id"], message)
            imported += int(created)
        url = data.get("@odata.nextLink")
        if not url:
            return graph_url(data["@odata.deltaLink"]), imported
    raise ProviderError("A sincronização terminou sem cursor de continuação.")


async def synchronize(account_id):
    found = rows("SELECT * FROM accounts WHERE id=?", (account_id,))
    if not found:
        raise ProviderError("A conta foi removida.")
    account = found[0]
    if account["demo"] or account["provider"] == "local":
        return {"imported": 0}
    try:
        token = await access_token(account)
        days = get_setting("preferences", {}).get("sync_days", 30)
        async with httpx.AsyncClient(timeout=45, headers={"Authorization": f"Bearer {token}"}) as client:
            cursor, imported = await (sync_gmail(client, account, days) if account["provider"] == "gmail" else sync_outlook(client, account, days))
        with connect() as db:
            db.execute("UPDATE accounts SET cursor=?,last_sync=?,error=NULL WHERE id=?", (cursor, now(), account_id))
        return {"imported": imported}
    except (ProviderError, httpx.HTTPError) as exc:
        message = str(exc) if isinstance(exc, ProviderError) else "Não foi possível alcançar o provedor. Verifique sua conexão."
        with connect() as db:
            db.execute("UPDATE accounts SET error=? WHERE id=?", (message, account_id))
        raise ProviderError(message) from exc
