"""The coding loop: ASI:One edits the store's repo through a few safe tools.

The model can list, read, search and edit files inside the repo, build the store
and run the Tester on a local copy. It cannot run arbitrary commands, touch files
outside the repo, or edit secrets, lockfiles or git internals.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, InternalServerError, RateLimitError

from .playbook import Fix
from .workspace import SKIP_DIRS, Stack, file_tree

MODEL = os.getenv("FIXER_MODEL", "asi1")
MAX_TOOL_CALLS = int(os.getenv("FIXER_MAX_TOOL_CALLS", "60"))
PROTECTED = re.compile(r"(^|/)(\.git|node_modules|\.venv|\.env[^/]*|package-lock\.json|yarn\.lock|pnpm-lock\.yaml)(/|$)", re.I)

SYSTEM = """You are the AgentReady Fixer, a careful senior web developer. You change an online store's code so that AI
shopping agents (which read plain HTML and do not run JavaScript) can find products, compare them, add one to a cart
and hand the shopper a checkout link that works on any device.

How to work:
1. Look before you change: list files, read the ones that matter (routes, templates, data, build config). Understand
   how the store gets its catalogue, renders pages and handles the cart.
2. Make the smallest clean change that fixes each selected problem, in the store's own style and stack. Reuse its
   data source, helpers, styles and naming. Don't add dependencies. Don't rewrite unrelated code or change prices,
   products, design or business rules. Never weaken or bypass security (CSRF, auth, validation) for any kind of
   client, agents included: an agent can load the page and send the form's token like a browser does.
   Never hard-code a domain: build absolute URLs from the request (or an existing config/env setting).
   Remove files you created but don't use.
3. For a fix marked "check first", confirm whether the store already does this; if it does, change nothing for it.
4. Call build to check your work compiles, then test_store to run the shopping Tester on the patched store. Read the
   report and keep fixing until the selected steps pass, or you are sure they can't with a reasonable change.
   The local test runs over plain http on 127.0.0.1. If something fails only because of that local setup (secure
   cookies, a fixed production domain, a missing secret), don't change the app for it; mention it in finish().
5. Finish with finish(): a short plain-English summary of what you changed and why, as a bullet list.

Edit with replace_in_file for small changes (exact text, must be unique) and write_file for new files or full
rewrites. Paths are relative to the repo root and use forward slashes."""

TOOLS = [
    {"name": "list_files", "description": "List the repo's files (optionally only under a folder).",
     "parameters": {"type": "object", "properties": {"folder": {"type": "string"}}}},
    {"name": "read_file", "description": "Read a text file, with line numbers. Long files: pass start_line/end_line.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}}, "required": ["path"]}},
    {"name": "search", "description": "Search all text files for a regular expression. Returns matching lines.",
     "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
    {"name": "write_file", "description": "Create a file or replace its whole content.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "replace_in_file", "description": "Replace one exact, unique piece of text in a file.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}}, "required": ["path", "old", "new"]}},
    {"name": "build", "description": "Build the store (or compile-check it) and return errors.", "parameters": {"type": "object", "properties": {}}},
    {"name": "test_store", "description": "Build, start the patched store locally and run the AI shopping Tester on it. Returns the step-by-step report.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "finish", "description": "Stop and summarise the changes for the pull request.",
     "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}},
]


@dataclass
class Session:
    ws: Path
    stack: Stack
    build: Callable[[], Awaitable[tuple[bool, str]]]
    test: Callable[[], Awaitable[str]]
    progress: Callable[[str], Awaitable[None]] | None = None
    summary: str = ""
    edits: int = 0
    log: list[str] = field(default_factory=list)

    def _path(self, rel: str) -> Path:
        rel = (rel or "").strip().lstrip("/").replace("\\", "/")
        p = (self.ws / rel).resolve()
        if p != self.ws.resolve() and self.ws.resolve() not in p.parents:
            raise ValueError("That path is outside the repo.")
        return p

    def _writable(self, rel: str) -> Path:
        if PROTECTED.search(rel.replace("\\", "/")):
            raise ValueError(f"{rel} is protected (secrets, lockfiles, dependencies or git); it can't be edited.")
        return self._path(rel)

    async def call(self, name: str, args: dict) -> str:
        try:
            if name == "list_files":
                folder = (args.get("folder") or "").strip("/")
                files = [f for f in file_tree(self.ws, 1000) if not folder or f.startswith(folder + "/")]
                return "\n".join(files[:400]) or "(no files)"
            if name == "read_file":
                p = self._path(args["path"])
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                a = max(1, int(args.get("start_line") or 1))
                b = min(len(lines), int(args.get("end_line") or a + 399))
                body = "\n".join(f"{i}\t{lines[i - 1]}" for i in range(a, b + 1))
                more = f"\n… ({len(lines)} lines in total; read more with start_line={b + 1})" if b < len(lines) else ""
                return (body + more) or "(empty file)"
            if name == "search":
                rx = re.compile(args["pattern"], re.I)
                hits = []
                for rel in file_tree(self.ws, 2000):
                    if rel.endswith("(binary)") or rel == "…":
                        continue
                    try:
                        for i, line in enumerate((self.ws / rel).read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                            if rx.search(line):
                                hits.append(f"{rel}:{i}: {line.strip()[:200]}")
                    except OSError:
                        continue
                    if len(hits) >= 80:
                        break
                return "\n".join(hits[:80]) or "No matches."
            if name == "write_file":
                p = self._writable(args["path"])
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(args["content"], encoding="utf-8", newline="")
                self.edits += 1
                self.log.append(f"wrote {args['path']}")
                return f"Wrote {args['path']} ({len(args['content'].splitlines())} lines)."
            if name == "replace_in_file":
                p = self._writable(args["path"])
                text = p.read_text(encoding="utf-8")
                old = args["old"]
                if old not in text and old.replace("\n", "\r\n") in text:
                    old, args["new"] = old.replace("\n", "\r\n"), args["new"].replace("\n", "\r\n")
                n = text.count(old)
                if n != 1:
                    return f"Not replaced: the text was found {n} times (it must be exactly once). Read the file and copy the exact text."
                p.write_text(text.replace(old, args["new"]), encoding="utf-8", newline="")
                self.edits += 1
                self.log.append(f"edited {args['path']}")
                return "Replaced."
            if name == "build":
                ok, out = await self.build()
                return "Build passed." if ok else "Build FAILED:\n" + out
            if name == "test_store":
                if self.progress:
                    await self.progress("Testing the patched store…")
                return await self.test()
            if name == "finish":
                self.summary = args.get("summary", "").strip()
                return "Done."
            return f"Unknown tool {name}."
        except Exception as err:  # the model sees the error and can recover
            return f"Error: {type(err).__name__}: {err}"


def _brief(stack: Stack, fixes: list[Fix], report_text: str, tree: list[str], extra: str = "") -> str:
    parts = [f"Stack: {stack.label}." + (" " + " ".join(stack.notes) if stack.notes else ""),
             "Repo files:\n" + "\n".join(tree[:250]),
             "What the AI shopping Tester saw on the store before your changes:\n" + report_text,
             "Fix these (selected by the store owner):"]
    for i, f in enumerate(fixes, 1):
        parts.append(f"### {i}. {f.title}{' (check first)' if f.check_first else ''}\nShould make these Tester steps pass: "
                     f"{', '.join(f.steps)}.\n{f.guidance}")
    if extra:
        parts.append(extra)
    return "\n\n".join(parts)


def _trim(messages: list[dict], budget: int = 180_000):
    """Keep the conversation within the model's context: shorten the oldest tool outputs first."""
    total = sum(len(m.get("content") or "") for m in messages)
    for m in messages[2:]:
        if total <= budget:
            break
        if m["role"] == "tool" and len(m["content"]) > 400:
            total -= len(m["content"]) - 60
            m["content"] = m["content"][:60] + " … [older output removed to save space]"


async def work(session: Session, fixes: list[Fix], report_text: str, extra: str = "",
               client: AsyncOpenAI | None = None) -> Session:
    client = client or AsyncOpenAI(base_url="https://api.asi1.ai/v1", api_key=os.environ["ASI1_API_KEY"], timeout=240)
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": _brief(session.stack, fixes, report_text, file_tree(session.ws), extra)}]
    tools = [{"type": "function", "function": t} for t in TOOLS]
    calls = 0
    nudged = False
    while calls < MAX_TOOL_CALLS and not session.summary:
        _trim(messages)
        resp = await _complete(client, messages=messages, tools=tools)
        msg = resp.choices[0].message
        entry = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            entry["tool_calls"] = [{"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                                   for c in msg.tool_calls]
        messages.append(entry)
        if not msg.tool_calls:
            if nudged:
                session.summary = session.summary or (msg.content or "").strip()
                break
            nudged = True
            messages.append({"role": "user", "content": "Use the tools to make and test the changes, then call finish()."})
            continue
        for c in msg.tool_calls:
            calls += 1
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
                result = "Error: the arguments were not valid JSON. Try again."
            else:
                result = await session.call(c.function.name, args)
            session.log.append(f"{c.function.name}({', '.join(f'{k}={str(v)[:60]!r}' for k, v in args.items() if k != 'content')})")
            messages.append({"role": "tool", "tool_call_id": c.id, "content": result[:30_000]})
    if not session.summary and session.edits:
        messages.append({"role": "user", "content": "Summarise what you changed and why, as a short bullet list for the pull request."})
        try:
            resp = await _complete(client, messages=messages)
            session.summary = (resp.choices[0].message.content or "").strip()
        except Exception:
            session.summary = "\n".join(f"- {line}" for line in session.log if line.startswith(("wrote", "edited")))
    return session


async def _complete(client: AsyncOpenAI, **kwargs):
    """One model call, retried: a dropped connection shouldn't end a fix that took ten minutes."""
    for attempt in range(4):
        try:
            return await client.chat.completions.create(model=MODEL, temperature=0.2, max_tokens=16000, **kwargs)
        except (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError):
            if attempt == 3:
                raise
            await asyncio.sleep(10 * (attempt + 1))
