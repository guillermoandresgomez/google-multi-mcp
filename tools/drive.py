from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

from auth import get_credentials


def _service(account: str):
    return build("drive", "v3", credentials=get_credentials(account))


def search_files(account: str, query: str, max_results: int = 10, parent_id: str | None = None) -> list[dict]:
    svc = _service(account)
    q = f"name contains '{query}' and trashed = false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    result = svc.files().list(
        q=q,
        pageSize=max_results,
        fields="files(id, name, mimeType, modifiedTime, webViewLink, size)",
        orderBy="modifiedTime desc",
    ).execute()
    return result.get("files", [])


def read_file_content(account: str, file_id: str) -> dict:
    svc = _service(account)
    metadata = svc.files().get(fileId=file_id, fields="id, name, mimeType").execute()
    mime = metadata.get("mimeType", "")
    if mime == "application/vnd.google-apps.document":
        content = svc.files().export(fileId=file_id, mimeType="text/plain").execute()
        return {"id": file_id, "name": metadata["name"], "mimeType": mime, "content": content.decode("utf-8")}
    elif mime == "application/vnd.google-apps.spreadsheet":
        content = svc.files().export(fileId=file_id, mimeType="text/csv").execute()
        return {"id": file_id, "name": metadata["name"], "mimeType": mime, "content": content.decode("utf-8")}
    elif mime.startswith("text/"):
        content = svc.files().get_media(fileId=file_id).execute()
        return {"id": file_id, "name": metadata["name"], "mimeType": mime, "content": content.decode("utf-8")}
    else:
        return {"id": file_id, "name": metadata["name"], "mimeType": mime,
                "content": f"[Binary file - {mime}. Use webViewLink to open.]"}


def list_recent_files(account: str, max_results: int = 10) -> list[dict]:
    svc = _service(account)
    result = svc.files().list(
        q="trashed = false",
        pageSize=max_results,
        fields="files(id, name, mimeType, modifiedTime, webViewLink)",
        orderBy="modifiedTime desc",
    ).execute()
    return result.get("files", [])


def create_file(account: str, name: str, content: str = "",
                 target_mime_type: str = "text/plain", parent_id: str | None = None) -> dict:
    """Create a file in Drive.

    - target_mime_type='application/vnd.google-apps.document' creates an editable Google Doc
      from the given plain-text content (Drive converts it automatically).
    - target_mime_type='text/markdown' or 'text/plain' creates a raw text/markdown file with
      no conversion (what you want for a cache file meant to be read back programmatically).
    - parent_id places the file inside that folder id (omit for My Drive root).
    """
    svc = _service(account)
    body = {"name": name, "mimeType": target_mime_type}
    if parent_id:
        body["parents"] = [parent_id]

    upload_mime = "text/plain" if target_mime_type == "application/vnd.google-apps.document" else target_mime_type
    media = MediaInMemoryUpload(content.encode("utf-8"), mimetype=upload_mime, resumable=False)
    return svc.files().create(body=body, media_body=media, fields="id, name, mimeType, webViewLink").execute()


def update_file_content(account: str, file_id: str, content: str) -> dict:
    """Replace the content of an existing Drive file, keeping its current type
    (a Google Doc stays a Google Doc; a plain text/markdown file stays plain text)."""
    svc = _service(account)
    meta = svc.files().get(fileId=file_id, fields="mimeType").execute()
    mime = meta["mimeType"]
    upload_mime = "text/plain" if mime == "application/vnd.google-apps.document" else mime
    media = MediaInMemoryUpload(content.encode("utf-8"), mimetype=upload_mime, resumable=False)
    return svc.files().update(fileId=file_id, media_body=media, fields="id, name, mimeType, webViewLink").execute()


def create_folder(account: str, name: str, parent_id: str | None = None) -> dict:
    svc = _service(account)
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    return svc.files().create(body=body, fields="id, name, webViewLink").execute()


def find_folder(account: str, name: str, parent_id: str | None = None) -> dict | None:
    svc = _service(account)
    escaped = name.replace("'", "\\'")
    q = f"name = '{escaped}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    result = svc.files().list(q=q, fields="files(id, name, webViewLink)", pageSize=5).execute()
    files = result.get("files", [])
    return files[0] if files else None


def find_or_create_folder(account: str, name: str, parent_id: str | None = None) -> dict:
    """Find a folder by exact name (optionally scoped inside parent_id), or create it if missing."""
    existing = find_folder(account, name, parent_id)
    if existing:
        return existing
    return create_folder(account, name, parent_id)


def trash_file(account: str, file_id: str) -> dict:
    """Move a file or folder to Drive's trash (recoverable, not permanent)."""
    svc = _service(account)
    result = svc.files().update(fileId=file_id, body={"trashed": True}, fields="id, name, trashed").execute()
    return result
