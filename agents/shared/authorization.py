"""Operator-enrolled requester/repository/origin bindings. No chat-based enrollment."""
import json
import os
from urllib.parse import urlsplit


def origin(site):
    try:
        u = urlsplit(site if "://" in site else "https://" + site)
        if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
            return None
        return (u.scheme, u.hostname.lower(), u.port or (443 if u.scheme == "https" else 80))
    except (ValueError, TypeError):
        return None


def bound_site(requester: str, repo: str) -> str | None:
    try:
        records = json.loads(os.getenv("FIXER_REQUESTER_BINDINGS", "[]"))
        if not isinstance(records, list): return None
        matches = [r for r in records if isinstance(r, dict) and r.get("requester") == requester
                   and str(r.get("repo", "")).lower() == repo.lower() and origin(r.get("site", ""))]
        return matches[0]["site"] if len(matches) == 1 else None
    except (ValueError, TypeError):
        return None


def authorized(requester: str, repo: str, site: str) -> bool:
    enrolled = bound_site(requester, repo)
    return bool(enrolled and origin(enrolled) == origin(site))
