"""File-based cottage blog. Grok (or anyone) adds Markdown under content/blog/."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "content" / "blog"
IMAGE_DIR = ROOT / "static" / "images" / "blog"
IMAGE_URL_PREFIX = "/static/images/blog/"

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    match = _FRONTMATTER.match(raw)
    if not match:
        return {}, raw.strip()
    meta: dict = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip().lower()] = value.strip().strip("\"'")
    return meta, match.group(2).strip()


def _as_date(value: str, fallback: date) -> date:
    text = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return fallback


def _as_bool(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or "note"


def _rewrite_images(body: str) -> str:
    def repl(match: re.Match) -> str:
        alt, url = match.group(1), match.group(2).strip()
        if url.startswith(("http://", "https://", "/")):
            return match.group(0)
        name = url.lstrip("./")
        if name.startswith("images/blog/"):
            name = name.split("/", 2)[-1]
        return f"![{alt}]({IMAGE_URL_PREFIX}{name})"

    return _MD_IMAGE.sub(repl, body)


def _image_src(path: str) -> str:
    path = (path or "").strip()
    if not path:
        return ""
    if path.startswith(("http://", "https://", "/")):
        return path
    if path.startswith("images/"):
        return f"/static/{path}"
    return f"{IMAGE_URL_PREFIX}{path.lstrip('./')}"


def _load_post(path: Path, include_drafts: bool = False) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    meta, body = _parse_frontmatter(raw)
    draft = _as_bool(meta.get("draft", ""))
    if draft and not include_drafts:
        return None
    title = meta.get("title") or path.stem.replace("-", " ").title()
    slug = _slugify(meta.get("slug") or path.stem)
    published = _as_date(meta.get("date", ""), date.fromtimestamp(path.stat().st_mtime))
    description = meta.get("description") or ""
    image_name = (meta.get("image") or "").strip()
    image = _image_src(image_name)
    # Escape raw HTML tags but leave '>' so Markdown blockquotes still work.
    safe_body = _rewrite_images(body.replace("&", "&amp;").replace("<", "&lt;"))
    html_body = markdown.markdown(
        safe_body,
        extensions=["nl2br", "sane_lists"],
        output_format="html",
    )
    return {
        "title": title,
        "slug": slug,
        "date": published,
        "description": description,
        "image": image,
        "image_name": image_name,
        "body": body,
        "html": html_body,
        "draft": draft,
        "path": path,
    }


def list_posts(include_drafts: bool = False) -> list[dict]:
    if not POSTS_DIR.is_dir():
        return []
    posts = []
    for path in POSTS_DIR.glob("*.md"):
        if path.name.lower() == "readme.md":
            continue
        post = _load_post(path, include_drafts=include_drafts)
        if post:
            posts.append(post)
    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    return posts


def get_post(slug: str, include_drafts: bool = False) -> dict | None:
    want = _slugify(slug)
    for post in list_posts(include_drafts=include_drafts):
        if post["slug"] == want:
            return post
    return None


def _fm_value(value: str) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\n", " ").strip()
    if not text:
        return '""'
    if any(ch in text for ch in ':#{}[]&*?|>!%@`"\''):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def save_post(
    *,
    title: str,
    slug: str = "",
    date_value: str = "",
    description: str = "",
    body: str = "",
    image: str = "",
    draft: bool = False,
    previous_slug: str = "",
) -> dict:
    title = (title or "").strip()
    if not title:
        raise ValueError("Title is required")
    slug = _slugify(slug or title)
    published = _as_date(date_value, date.today())
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = POSTS_DIR / f"{slug}.md"
    previous = _slugify(previous_slug) if previous_slug else ""
    if dest.exists() and previous and previous != slug:
        raise ValueError("That web address is already used by another note")
    if dest.exists() and not previous:
        raise ValueError("That web address is already used by another note")
    image = (image or "").strip()
    if image.startswith("/static/images/blog/"):
        image = image.rsplit("/", 1)[-1]
    parts = [
        "---",
        f"title: {_fm_value(title)}",
        f"slug: {slug}",
        f"date: {published.isoformat()}",
        f"description: {_fm_value(description)}",
        f"image: {_fm_value(image)}",
        f"draft: {'true' if draft else 'false'}",
        "---",
        "",
        (body or "").replace("\r\n", "\n").strip(),
        "",
    ]
    dest.write_text("\n".join(parts), encoding="utf-8")
    if previous and previous != slug:
        old = POSTS_DIR / f"{previous}.md"
        if old.exists() and old != dest:
            old.unlink()
    loaded = _load_post(dest, include_drafts=True)
    if not loaded:
        raise ValueError("Saved note could not be read back")
    return loaded


def delete_post(slug: str) -> bool:
    post = get_post(slug, include_drafts=True)
    if not post:
        return False
    path = post["path"]
    try:
        path.unlink()
    except OSError:
        return False
    return True


def save_images(files) -> list[str]:
    from uuid import uuid4

    from werkzeug.utils import secure_filename

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    for storage in files:
        if not storage or not getattr(storage, "filename", None):
            continue
        ext = Path(storage.filename).suffix.lower()
        if ext not in allowed:
            continue
        if ext == ".jpeg":
            ext = ".jpg"
        safe = secure_filename(Path(storage.filename).stem) or "photo"
        name = f"{safe[:40]}-{uuid4().hex[:8]}{ext}"
        dest = IMAGE_DIR / name
        storage.save(str(dest))
        saved.append(name)
    return saved


def append_images_to_body(body: str, filenames: list[str]) -> str:
    text = (body or "").rstrip()
    chunks = []
    for name in filenames:
        marker = f"]({name})"
        url = f"]({IMAGE_URL_PREFIX}{name})"
        if marker in text or url in text:
            continue
        alt = Path(name).stem.replace("-", " ")
        chunks.append(f"![{alt}]({name})")
    if not chunks:
        return (body or "").strip()
    if text:
        text += "\n\n"
    return text + "\n\n".join(chunks) + "\n"
