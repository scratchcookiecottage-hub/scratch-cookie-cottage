"""File-based cottage blog. Grok (or anyone) adds Markdown under content/blog/."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "content" / "blog"
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


def _load_post(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    meta, body = _parse_frontmatter(raw)
    if _as_bool(meta.get("draft", "")):
        return None
    title = meta.get("title") or path.stem.replace("-", " ").title()
    slug = _slugify(meta.get("slug") or path.stem)
    published = _as_date(meta.get("date", ""), date.fromtimestamp(path.stat().st_mtime))
    description = meta.get("description") or ""
    image = _image_src(meta.get("image", ""))
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
        "html": html_body,
        "path": path,
    }


def list_posts() -> list[dict]:
    if not POSTS_DIR.is_dir():
        return []
    posts = []
    for path in POSTS_DIR.glob("*.md"):
        if path.name.lower() == "readme.md":
            continue
        post = _load_post(path)
        if post:
            posts.append(post)
    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    return posts


def get_post(slug: str) -> dict | None:
    want = _slugify(slug)
    for post in list_posts():
        if post["slug"] == want:
            return post
    return None
