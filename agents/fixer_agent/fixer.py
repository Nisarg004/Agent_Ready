"""The Fixer's job, start to finish.

    diagnose()  clone the store's repo, work out its stack, let the Tester shop on the
                live site, and turn what failed into a plan of fixes for the owner to pick.
    apply()     run the original store locally and test it (before), let ASI:One make the
                chosen fixes, rebuild and test again (after), retry if needed, then open a
                pull request with the before/after proof. Nothing is merged or deployed.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import stat
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from tester_agent.shopper import Report, format_report, run as shop

from . import coder, github, playbook, workspace
from .playbook import Fix, Plan
from .workspace import SKIP_DIRS, Server, Stack

WORK_DIR = Path(os.getenv("FIXER_WORK_DIR") or Path(tempfile.gettempdir()) / "agentready-fixer")
ROUNDS = int(os.getenv("FIXER_ROUNDS", "3"))

Progress = Callable[[str], Awaitable[None]]


async def _quiet(_: str):
    pass


@dataclass
class Job:
    site: str
    task: str
    repo: github.Repo
    ws: Path
    stack: Stack
    live: dict
    live_text: str
    plan: Plan
    created: float = field(default_factory=time.time)


@dataclass
class Result:
    ok: bool
    message: str
    before: dict | None = None
    after: dict | None = None
    pr_url: str | None = None
    branch: str | None = None
    files: list[str] = field(default_factory=list)
    summary: str = ""
    diff: str = ""


def _rmtree(p: Path):
    def onerror(func, path, _):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    shutil.rmtree(p, onerror=onerror)


async def diagnose(site: str, owner: str, name: str, task: str, progress: Progress = _quiet) -> Job:
    repo = await github.get_repo(owner, name)
    if not repo.can_push:
        raise github.GitHubError(f"I can read {repo.full} but can't push to it. Give the Fixer write access (add it as a collaborator) and try again.")
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    ws = WORK_DIR / f"{repo.name}-{int(time.time())}"
    await progress(f"Reading the code of {repo.full} and testing {site} live…")
    clone = asyncio.to_thread(github.clone, repo, ws)
    live, _ = await asyncio.gather(shop(site, task), clone)
    stack = workspace.detect(ws)
    live_d = live.to_dict()
    return Job(site, task, repo, ws, stack, live_d, format_report(live), playbook.plan(live_d, stack))


def plan_text(job: Job) -> str:
    lines = [f"## Fix plan for {job.repo.full}", "",
             f"Stack: **{job.stack.label}**. Live shopping test: **{job.live['passed']} / 5 steps**.", ""]
    if not job.plan.fixes:
        lines.append("Nothing for me to fix: the shopping test found no problems I can solve in code.")
    for i, f in enumerate(job.plan.fixes, 1):
        lines.append(f"{i}. **{f.title}**{' (I will check first, it may already work)' if f.check_first else ''}  \n   {f.why}")
    for n in job.plan.notes:
        lines += ["", f"ℹ️ {n}"]
    if job.plan.fixes:
        lines += ["", "Reply **apply all**, or pick some, e.g. **apply 1,3**. I'll make the changes, test the patched store "
                      "with the Tester, and open a pull request for you to review. Nothing goes live until you merge it."]
    return "\n".join(lines)


def pick(job: Job, text: str) -> list[Fix]:
    if re.search(r"\ball\b", text, re.I):
        return list(job.plan.fixes)
    nums = {int(n) for n in re.findall(r"\d+", text)}
    return [f for i, f in enumerate(job.plan.fixes, 1) if i in nums]


async def _test_local(ws: Path, stack: Stack, site_task: str) -> Report:
    async with Server(ws, stack) as srv:
        return await shop(srv.url, site_task)


def _exclude_build_dirs(ws: Path):
    """Make sure installs and builds never end up in the commit, even if .gitignore misses them."""
    excl = ws / ".git" / "info" / "exclude"
    excl.parent.mkdir(parents=True, exist_ok=True)
    excl.write_text("\n".join(f"{d}/" for d in sorted(SKIP_DIRS - {".git"})) + "\n*-server.log\n", encoding="utf-8")


async def apply(job: Job, fixes: list[Fix], progress: Progress = _quiet, open_pr: bool = True) -> Result:
    ws, stack = job.ws, job.stack
    if stack.kind == "unknown":
        return Result(False, "I couldn't recognise how this store is built, so I can't run and test it safely.")
    _exclude_build_dirs(ws)

    await progress(f"Installing the store ({stack.label})…")
    ok, out = await workspace.install(ws, stack)
    if not ok:
        return Result(False, "Installing the store's dependencies failed:\n```\n" + out[-1200:] + "\n```")
    ok, out = await workspace.build(ws, stack)
    if not ok:
        return Result(False, "The store doesn't build as it is, before any change of mine:\n```\n" + out[-1200:] + "\n```")
    await progress("Running the original store locally and testing it (before)…")
    before = await _test_local(ws, stack, job.task)

    last: dict = {"report": before}

    async def build():
        return await workspace.build(ws, stack)

    async def test() -> str:
        ok, out = await workspace.build(ws, stack)
        if not ok:
            return "Build FAILED, so the store can't be tested:\n" + out
        try:
            report = await _test_local(ws, stack, job.task)
        except RuntimeError as err:
            return str(err)
        last["report"] = report
        return format_report(report)

    targets = {s for f in fixes for s in f.steps}
    session = coder.Session(ws, stack, build, test, progress)
    after: Report | None = None
    feedback = ""
    for round_no in range(1, ROUNDS + 1):
        await progress(f"Making the changes (round {round_no} of up to {ROUNDS})…" if round_no > 1 else "Making the changes with ASI:One…")
        extra = feedback
        if after is not None and not feedback:
            still = [s for s in after.steps if s.name in targets and not s.passed]
            extra = ("Your previous changes are still in the repo. The Tester's latest run on the patched store:\n"
                     + format_report(after) + "\n\nThese selected steps still fail: " + ", ".join(s.name for s in still)
                     + ". Find out why and fix it.")
        session.summary, feedback = "", ""
        await coder.work(session, fixes, format_report(before), extra)
        if not github.changed_files(ws):
            continue
        await progress("Checking the result: building and testing the patched store…")
        ok, out = await workspace.build(ws, stack)
        if not ok:
            after = None
            feedback = "Your changes are still in the repo, but the build now FAILS:\n" + out + "\nFix the build first."
            continue
        after = await _test_local(ws, stack, job.task)
        if all(s.passed for s in after.steps if s.name in targets):
            break

    files = github.changed_files(ws)
    if not files:
        return Result(False, "I couldn't find a change that works, so I didn't touch your code.", before.to_dict())
    if after is None:
        return Result(False, "My changes didn't build, so I stopped without opening a pull request.", before.to_dict(), files=files)
    if after.passed <= before.passed:
        return Result(False, f"My changes didn't improve the shopping test ({before.passed}/5 before, {after.passed}/5 after), "
                             "so I didn't open a pull request.", before.to_dict(), after.to_dict(), files=files)

    result = Result(True, "", before.to_dict(), after.to_dict(), files=files, summary=session.summary, diff=github.diff(ws))
    if not open_pr:
        result.message = "Dry run: changes made and tested locally, no pull request opened."
        return result
    await progress("Opening a pull request…")
    branch = f"agentready/fix-{time.strftime('%Y%m%d-%H%M')}"
    title = f"Make the store usable by AI shopping agents ({before.passed}/5 → {after.passed}/5)"
    await asyncio.to_thread(github.commit_and_push, ws, branch, title)
    result.pr_url = await github.open_pr(job.repo, branch, title, pr_body(job, fixes, before, after, session.summary))
    result.branch = branch
    return result


def _row(b, a) -> str:
    mark = lambda s: "✅" if s.passed else "❌"
    return f"| {b.name} | {mark(b)} | {mark(a)} |"


def pr_body(job: Job, fixes: list[Fix], before: Report, after: Report, summary: str) -> str:
    rows = "\n".join(_row(b, a) for b, a in zip(before.steps, after.steps))
    picked = "\n".join(f"- **{f.title}**: {f.why}" for f in fixes)
    after_detail = "\n".join(f"{'✅' if s.passed else '❌'} **{s.name}**: {s.detail}" for s in after.steps)
    return f"""Opened by the **AgentReady Fixer** agent.

AI shopping agents (ChatGPT, Claude, Perplexity, Gemini…) read your site's HTML and mostly don't run JavaScript.
The AgentReady Tester tried to shop on this store: *“{job.task}”*.

## Result: {before.passed}/5 → {after.passed}/5

| Step | Before | After |
|---|---|---|
{rows}

Both runs used the same local build of this repo (before and after this change) and the same Tester.

## What was fixed
{picked}

## Changes
{summary or '- See the diff.'}

## Tester report after the change
{after_detail}

Please review and test before merging. After it is deployed, ask the Fixer to **retest** {job.site} to confirm it live.
"""


def cleanup(job: Job):
    try:
        _rmtree(job.ws)
    except OSError:
        pass
