"""Find the website in a chat message.

Messages (and ASI:One's own commentary) mention files and frameworks like
package.json or Next.js, which look like domains. Those are never websites.
"""

from __future__ import annotations

import re

SITE_RE = re.compile(r"(https?://[^\s<>\"'`]+|(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>\"'`]*)?)", re.I)

# Endings of file names, never of a website we'd scan.
FILE_SUFFIXES = {
    "js", "mjs", "cjs", "jsx", "ts", "tsx", "json", "py", "md", "mdx", "txt", "html", "htm", "css", "scss",
    "yml", "yaml", "toml", "lock", "env", "sh", "xml", "csv", "png", "jpg", "jpeg", "gif", "svg", "webp",
    "ico", "zip", "map", "log", "ini", "cfg", "conf", "vue", "svelte", "go", "rs", "rb", "php", "java",
}


def is_site(candidate: str) -> bool:
    host = re.sub(r"^https?://", "", candidate.strip(), flags=re.I).split("/")[0].split(":")[0].lower()
    if "." not in host or "github.com" in host:
        return False
    return host.rsplit(".", 1)[-1] not in FILE_SUFFIXES


def find_site_match(text: str) -> re.Match | None:
    for m in SITE_RE.finditer(text):
        if is_site(m.group(1)):
            return m
    return None


def find_site(text: str) -> str | None:
    m = find_site_match(text)
    return m.group(1).rstrip(".,;:!?)") if m else None
