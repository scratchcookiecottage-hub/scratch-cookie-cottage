"""Google Drive helper for factory drop uploads and the shots-needed doc."""

from __future__ import annotations

import io
import json
import os
from typing import Any

from config import Config

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents.readonly",
]

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


def drive_ready() -> bool:
    return bool(Config.google_service_account_info())


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


def _drive():
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=_credentials(), cache_discovery=False)


def upload_to_drop(filename: str, data: bytes, mime: str | None = None) -> dict[str, Any]:
    from googleapiclient.http import MediaIoBaseUpload

    folder = Config.FACTORY_DRIVE_DROP_FOLDER_ID
    if not folder:
        raise RuntimeError("FACTORY_DRIVE_DROP_FOLDER_ID is not set")
    ext = os.path.splitext(filename)[1].lower()
    mime = mime or MIME_BY_EXT.get(ext) or "application/octet-stream"
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=True)
    body = {"name": filename, "parents": [folder]}
    created = (
        _drive()
        .files()
        .create(
            body=body,
            media_body=media,
            fields="id,name,webViewLink,mimeType,createdTime",
            supportsAllDrives=True,
        )
        .execute()
    )
    return created


def list_drop_files(limit: int = 20) -> list[dict[str, Any]]:
    folder = Config.FACTORY_DRIVE_DROP_FOLDER_ID
    if not folder or not drive_ready():
        return []
    resp = (
        _drive()
        .files()
        .list(
            q=f"'{folder}' in parents and trashed = false",
            orderBy="createdTime desc",
            pageSize=limit,
            fields="files(id,name,mimeType,createdTime,webViewLink)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    return list(resp.get("files") or [])


def read_shots_doc() -> str:
    doc_id = Config.FACTORY_SHOTS_DOC_ID
    if not doc_id:
        raise RuntimeError("FACTORY_SHOTS_DOC_ID is not set")
    content = (
        _drive()
        .files()
        .export(fileId=doc_id, mimeType="text/plain")
        .execute()
    )
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return str(content or "")
