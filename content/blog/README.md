# Cottage blog (for Grok)

Grok publishes SEO notes by adding Markdown files here and photos in `static/images/blog/`. Then commit, push, and `git pull` + **Reload** on PythonAnywhere.

Live URLs:

- Index: `/blog`
- One note: `/blog/your-slug`

## New article

1. Save photos as web JPEGs in `static/images/blog/` (short names, no spaces).
2. Add `content/blog/your-slug.md`:

```markdown
---
title: White Miso Peanut Butter, with chopped peanuts
slug: white-miso-peanut-butter
date: 2026-09-04
description: Our White Miso Peanut Butter cookie now includes chopped peanuts and almond extract.
image: peanuts-on-cookie.jpg
draft: false
---

Opening paragraph with the main keyword (Austin cottage cookies, the flavor name, pickup).

![Chopped peanuts on a cookie](peanuts-on-cookie.jpg)

More detail. Link to [order cookies](/order) once.

## Subheading

Keep it useful: ingredients story, weekend pickup, cottage-food notes. Not a sales dump.
```

3. `draft: true` hides the note. Omit `draft` or set `false` to publish.
4. `image:` is the social/hero photo (filename in `static/images/blog/`, or `images/flavor.jpg`).
5. In the body, `![alt](file.jpg)` looks in `static/images/blog/`. Use `/static/images/peanut_butter.jpg` for existing site photos. Always write real alt text.
6. Do not use raw HTML.

## SEO checklist

- Unique `title` and `description` (about 150 characters).
- Slug is lowercase-hyphenated and stable (do not rename after it ranks).
- One clear topic per note.
- At least one photo with alt text.
- Natural mention of Austin / cottage kitchen / the cookie names when it is true.
- Link to `/order` or `/story` where it helps a reader.

Sitemap and robots pick up published notes automatically (`/sitemap.xml`).
