"""Google Drive helper via requests + AuthorizedSession.

PythonAnywhere free tier cannot reach Google through httplib2/googleapiclient
([Errno 101] Network is unreachable). Route all Drive calls through
http://proxy.server:3128 using google.auth.transport.requests.AuthorizedSession.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import quote

from config import Config

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents.readonly",
]

PA_PROXY = os.getenv("PA_HTTP_PROXY", "http://proxy.server:3128")

MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".heic": "image/heic",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".m4v": "video/x-m4v",
    ".webm": "video/webm",
}

DRIVE = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3"


def google_client_installed() -> bool:
    try:
        from google.oauth2 import service_account  # noqa: F401
        from google.auth.transport.requests import AuthorizedSession  # noqa: F401
        import requests  # noqa: F401

        return True
    except ImportError:
        return False


def drive_ready() -> bool:
    return google_client_installed() and bool(Config.google_service_account_info())


def drive_status() -> str:
    if not google_client_installed():
        return (
            "Google auth/requests is not installed. In a PythonAnywhere Bash console, "
            "activate your virtualenv and run: pip install google-auth requests"
        )
    if not Config.google_service_account_info():
        return (
            "No service-account JSON found. Upload google-sa.json to "
            "secrets/google-sa.json on the server (or set GOOGLE_SERVICE_ACCOUNT_FILE)."
        )
    return ""


def decode_drive_text(raw) -> str:
    """Drive export is UTF-8, often with a BOM. Never treat it as Latin-1."""
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        text = raw.decode("utf-8-sig")
    else:
        text = str(raw)
        if text.startswith("\ufeff"):
            text = text.lstrip("\ufeff")
        if "ï»¿" in text[:8] or "â€" in text or "Ã" in text:
            try:
                text = text.encode("latin-1").decode("utf-8-sig")
            except UnicodeError:
                pass
    return text.replace("\ufeff", "")


def _credentials():
    from google.oauth2 import service_account

    info = Config.google_service_account_info()
    if not info:
        raise RuntimeError(
            "Google service account is not set. Add GOOGLE_SERVICE_ACCOUNT_FILE "
            "or GOOGLE_SERVICE_ACCOUNT_JSON, then share the Drive drop folder "
            "and shots doc with that service account email."
        )
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)


def _session():
    from google.auth.transport.requests import AuthorizedSession

    session = AuthorizedSession(_credentials())
    session.trust_env = True
    session.proxies.update({"http": PA_PROXY, "https": PA_PROXY})
    return session


def upload_to_drop(filename: str, data: bytes, mime: str | None = None) -> dict[str, Any]:
    folder = Config.FACTORY_DRIVE_DROP_FOLDER_ID
    if not folder:
        raise RuntimeError("FACTORY_DRIVE_DROP_FOLDER_ID is not set")
    ext = os.path.splitext(filename)[1].lower()
    mime = mime or MIME_BY_EXT.get(ext) or "application/octet-stream"
    boundary = "scc_drive_boundary"
    meta = json.dumps({"name": filename, "parents": [folder]}).encode("utf-8")
    body = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
    ).encode("utf-8")
    body += meta + b"\r\n"
    body += (
        f"--{boundary}\r\n"
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8")
    body += data + f"\r\n--{boundary}--".encode("utf-8")
    resp = _session().post(
        f"{UPLOAD}/files",
        params={
            "uploadType": "multipart",
            "supportsAllDrives": "true",
            "fields": "id,name,webViewLink,mimeType,createdTime",
        },
        data=body,
        headers={"Content-Type": f"multipart/related; boundary={boundary}"},
        timeout=180,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Drive upload failed ({resp.status_code}): {resp.text[:400]}")
    return resp.json()


def list_drop_files(limit: int = 20) -> list[dict[str, Any]]:
    folder = Config.FACTORY_DRIVE_DROP_FOLDER_ID
    if not folder or not drive_ready():
        return []
    resp = _session().get(
        f"{DRIVE}/files",
        params={
            "q": f"'{folder}' in parents and trashed = false",
            "orderBy": "createdTime desc",
            "pageSize": str(limit),
            "fields": "files(id,name,mimeType,createdTime,webViewLink)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Drive list failed ({resp.status_code}): {resp.text[:400]}")
    return list((resp.json() or {}).get("files") or [])


def read_shots_doc() -> str:
    doc_id = Config.FACTORY_SHOTS_DOC_ID
    if not doc_id:
        raise RuntimeError("FACTORY_SHOTS_DOC_ID is not set")
    resp = _session().get(
        f"{DRIVE}/files/{quote(doc_id)}/export",
        params={"mimeType": "text/plain"},
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Drive export failed ({resp.status_code}): {resp.text[:400]}")
    # Prefer raw bytes so we control UTF-8 + BOM ourselves.
    return decode_drive_text(resp.content)
