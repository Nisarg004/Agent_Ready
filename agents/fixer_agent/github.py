"""GitHub access for the Fixer: clone a store's repo, push a branch, open a pull request.

The token comes from GITHUB_TOKEN, or from the GitHub CLI's login (`gh auth token`)
when that is set up on this machine. It is never written to disk or logs: git gets
it through an auth header on each command.
"""

from __future__ import annotations

import base64
import fnmatch
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import httpx

API = "https://api.github.com"
REPO_RE = re.compile(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/#?].*)?$", re.I)


class GitHubError(RuntimeError):
    pass


@dataclass
class Repo:
    owner: str
    name: str
    default_branch: str = "main"
    can_push: bool = False
    homepage: str = ""

    @property
    def full(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def url(self) -> str:
        return f"https://github.com/{self.full}"


def parse_repo(text: str) -> tuple[str, str] | None:
    for word in text.split():
        m = REPO_RE.search(word.strip("<>()[]`'\".,"))
        if m:
            return m.group(1), m.group(2)
    return None


_token: str | None = None


def token() -> str:
    global _token
    if _token is None:
        _token = os.getenv("GITHUB_TOKEN", "").strip()
        if not _token and shutil.which("gh"):
            out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
            _token = out.stdout.strip() if out.returncode == 0 else ""
    if not _token:
        raise GitHubError("No GitHub access is set up for the Fixer (GITHUB_TOKEN).")
    return _token


def _headers() -> dict:
    return {"Authorization": f"Bearer {token()}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


async def get_repo(owner: str, name: str) -> Repo:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{API}/repos/{owner}/{name}", headers=_headers())
    if r.status_code == 404:
        raise GitHubError(f"I can't see github.com/{owner}/{name}. It doesn't exist, or the Fixer hasn't been given access to it.")
    r.raise_for_status()
    d = r.json()
    return Repo(d["owner"]["login"], d["name"], d.get("default_branch") or "main", bool(d.get("permissions", {}).get("push")),
                d.get("homepage") or "")


def allowed(owner: str, name: str) -> bool:
    """Only repos whose owners connected them (FIXER_ALLOWED_REPOS, e.g. "me/shop,me/*-store") are worked on."""
    patterns = [p.strip().lower() for p in os.getenv("FIXER_ALLOWED_REPOS", "").split(",") if p.strip()]
    return any(fnmatch.fnmatch(f"{owner}/{name}".lower(), p) for p in patterns)


def _git(args: list[str], cwd: Path | None = None, auth: bool = False) -> str:
    cmd = ["git"]
    if auth:
        basic = base64.b64encode(f"x-access-token:{token()}".encode()).decode()
        cmd += ["-c", f"http.extraHeader=Authorization: Basic {basic}"]
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    out = subprocess.run(cmd + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if out.returncode != 0:
        # Never echo the command: it may carry the auth header.
        raise GitHubError(f"git {args[0]} failed: {out.stderr.strip()[-400:]}")
    return out.stdout


def clone(repo: Repo, dest: Path) -> None:
    _git(["clone", "--depth", "1", "--branch", repo.default_branch, f"{repo.url}.git", str(dest)], auth=True)


def changed_files(ws: Path) -> list[str]:
    out = _git(["status", "--porcelain"], cwd=ws)
    return [line[3:].strip().strip('"') for line in out.splitlines() if line.strip()]


def untracked_files(ws: Path) -> list[str]:
    """New files, listed one by one (not collapsed to their folder), including ones marked intent-to-add."""
    out = _git(["status", "--porcelain", "--untracked-files=all"], cwd=ws)
    return [line[3:].strip().strip('"') for line in out.splitlines() if line[:2] in ("??", " A", "A ", "AM")]


def diff(ws: Path, limit: int = 60_000) -> str:
    _git(["add", "-A", "-N"], cwd=ws)
    return _git(["diff"], cwd=ws)[:limit]


def commit_and_push(ws: Path, branch: str, message: str) -> None:
    name = os.getenv("FIXER_GIT_NAME", "AgentReady Fixer")
    email = os.getenv("FIXER_GIT_EMAIL", "agentready-fixer@users.noreply.github.com")
    _git(["checkout", "-b", branch], cwd=ws)
    _git(["add", "-A"], cwd=ws)
    _git(["-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-q", "-m", message], cwd=ws)
    _git(["push", "-q", "origin", branch], cwd=ws, auth=True)


async def open_pr(repo: Repo, branch: str, title: str, body: str, draft: bool = False) -> str:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{API}/repos/{repo.full}/pulls", headers=_headers(),
                         json={"title": title, "head": branch, "base": repo.default_branch, "body": body, "draft": draft})
        if draft and r.status_code == 422 and "draft" in r.text.lower():
            # Draft PRs aren't available on every plan: open a normal one; its title and body still say "Draft".
            r = await c.post(f"{API}/repos/{repo.full}/pulls", headers=_headers(),
                             json={"title": title, "head": branch, "base": repo.default_branch, "body": body})
    if r.status_code >= 300:
        raise GitHubError(f"GitHub refused the pull request ({r.status_code}): {r.text[:300]}")
    return r.json()["html_url"]


def pr_number(url: str) -> int | None:
    m = re.search(r"/pull/(\d+)", url or "")
    return int(m.group(1)) if m else None


async def merge_pr(owner: str, name: str, number: int) -> None:
    raise GitHubError("Agent merging is disabled; review and merge in GitHub.")
