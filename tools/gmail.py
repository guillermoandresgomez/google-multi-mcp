import base64
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.utils import formataddr
from email.header import Header
from email import encoders

from googleapiclient.discovery import build

from auth import get_credentials, get_account_email, _load_config


def _service(account: str):
    return build("gmail", "v1", credentials=get_credentials(account))


def _get_sender_info(account: str) -> dict:
    """Fetch sender display name and signature from Gmail settings.
    Falls back to display_name from config.json if Gmail has no displayName."""
    svc = _service(account)
    email = get_account_email(account)
    config = _load_config()
    config_name = config["accounts"][account].get("display_name", "")
    try:
        send_as = svc.users().settings().sendAs().get(userId="me", sendAsEmail=email).execute()
        gmail_name = send_as.get("displayName", "")
        return {
            "name": gmail_name or config_name,
            "email": email,
            "signature": send_as.get("signature", ""),
        }
    except Exception:
        return {"name": config_name, "email": email, "signature": ""}


def _build_message(account: str, to: str, subject: str, body: str,
                   attachments: list[str] | None = None) -> str:
    sender_info = _get_sender_info(account)
    signature_html = sender_info["signature"]
    email_addr = sender_info["email"]

    # Build the text/content part
    if signature_html:
        content = MIMEMultipart("alternative")
        body_html = body.replace("\n", "<br>")
        content.attach(MIMEText(body, "plain", "utf-8"))
        content.attach(MIMEText(f"{body_html}<br><br>--<br>{signature_html}", "html", "utf-8"))
    else:
        content = MIMEText(body, "plain", "utf-8")

    # Wrap in multipart/mixed only if there are attachments
    if attachments:
        msg = MIMEMultipart("mixed")
        msg.attach(content)
        for path in attachments:
            filename = os.path.basename(path)
            with open(path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            # RFC 2231 encoding for non-ASCII filenames (e.g. accented chars)
            part.add_header("Content-Disposition", "attachment",
                            filename=("utf-8", "", filename))
            msg.attach(part)
    else:
        msg = content

    msg["to"] = to
    msg["subject"] = Header(subject, "utf-8")
    msg["from"] = formataddr((sender_info["name"], email_addr))

    # as_bytes() is more reliable than as_string().encode() for non-ASCII content
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")


def search_emails(account: str, query: str, max_results: int = 10) -> list[dict]:
    svc = _service(account)
    result = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    messages = result.get("messages", [])
    output = []
    for msg in messages:
        detail = svc.users().messages().get(userId="me", id=msg["id"], format="metadata",
                                            metadataHeaders=["Subject", "From", "Date"]).execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        output.append({
            "id": msg["id"],
            "threadId": msg["threadId"],
            "subject": headers.get("Subject", ""),
            "from": headers.get("From", ""),
            "date": headers.get("Date", ""),
            "snippet": detail.get("snippet", ""),
        })
    return output


def read_email(account: str, message_id: str) -> dict:
    svc = _service(account)
    msg = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    body = ""
    payload = msg["payload"]
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain" and "data" in part.get("body", {}):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                break
    elif "body" in payload and "data" in payload["body"]:
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
    return {
        "id": msg["id"],
        "threadId": msg["threadId"],
        "subject": headers.get("Subject", ""),
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "date": headers.get("Date", ""),
        "body": body,
        "labels": msg.get("labelIds", []),
    }


def read_thread(account: str, thread_id: str) -> dict:
    svc = _service(account)
    thread = svc.users().threads().get(userId="me", id=thread_id, format="metadata",
                                       metadataHeaders=["Subject", "From", "Date"]).execute()
    messages = []
    for msg in thread.get("messages", []):
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        messages.append({
            "id": msg["id"],
            "subject": headers.get("Subject", ""),
            "from": headers.get("From", ""),
            "date": headers.get("Date", ""),
            "snippet": msg.get("snippet", ""),
        })
    return {"threadId": thread_id, "messages": messages}


def send_email(account: str, to: str, subject: str, body: str,
               attachments: list[str] | None = None) -> dict:
    svc = _service(account)
    raw = _build_message(account, to, subject, body, attachments)
    sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"id": sent["id"], "threadId": sent.get("threadId", "")}


def create_draft(account: str, to: str, subject: str, body: str,
                 attachments: list[str] | None = None) -> dict:
    svc = _service(account)
    raw = _build_message(account, to, subject, body, attachments)
    draft = svc.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return {"id": draft["id"], "message_id": draft["message"]["id"]}


def list_drafts(account: str, max_results: int = 20) -> list[dict]:
    svc = _service(account)
    result = svc.users().drafts().list(userId="me", maxResults=max_results).execute()
    output = []
    for d in result.get("drafts", []):
        detail = svc.users().messages().get(userId="me", id=d["message"]["id"], format="metadata",
                                            metadataHeaders=["Subject", "To", "Date"]).execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        output.append({
            "id": d["id"],
            "message_id": d["message"]["id"],
            "subject": headers.get("Subject", ""),
            "to": headers.get("To", ""),
            "date": headers.get("Date", ""),
            "snippet": detail.get("snippet", ""),
        })
    return output


def delete_draft(account: str, draft_id: str) -> dict:
    """Permanently delete a draft (not sent to Trash; irreversible)."""
    svc = _service(account)
    svc.users().drafts().delete(userId="me", id=draft_id).execute()
    return {"status": "deleted", "id": draft_id}


def list_labels(account: str) -> list[dict]:
    svc = _service(account)
    result = svc.users().labels().list(userId="me").execute()
    return [{"id": l["id"], "name": l["name"]} for l in result.get("labels", [])]


def archive_email(account: str, message_id: str) -> dict:
    svc = _service(account)
    svc.users().messages().modify(userId="me", id=message_id,
                                  body={"removeLabelIds": ["INBOX"]}).execute()
    return {"status": "archived", "id": message_id}


def mark_read(account: str, message_id: str, read: bool = True) -> dict:
    svc = _service(account)
    if read:
        body = {"removeLabelIds": ["UNREAD"]}
    else:
        body = {"addLabelIds": ["UNREAD"]}
    svc.users().messages().modify(userId="me", id=message_id, body=body).execute()
    return {"status": "read" if read else "unread", "id": message_id}
