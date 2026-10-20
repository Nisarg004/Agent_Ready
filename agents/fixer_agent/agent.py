"""AgentReady Fixer as a Fetch.ai uAgent speaking the Agent Chat Protocol.

Chat with it in ASI:One:
    "Fix voltkart.onrender.com, code at github.com/me/voltkart-store"   -> tests the site, replies with a fix plan
    "apply all"  or  "apply 1,3"                                         -> makes, tests and opens a pull request
    "retest"                                                             -> runs the shopping test on the live site again

Run it:   python fixer_agent/agent.py
Settings: agents/.env (FIXER_AGENT_SEED, FIXER_ALLOWED_REPOS, GITHUB_TOKEN, ASI1_API_KEY).
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from uagents import Agent, Context, Protocol  # noqa: E402
from uagents_core.contrib.protocols.chat import (  # noqa: E402
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from fixer_agent import fixer, github  # noqa: E402
from tester_agent.agent import URL_RE  # noqa: E402
from tester_agent.shopper import format_report, run as shop  # noqa: E402

PROFILE_README = "fixer.md"
PROFILE_DESCRIPTION = "Fixes online stores so AI shopping agents can buy from them: tests the site, changes the code on GitHub, proves it with a before/after shopping test, and opens a pull request."
JOB_TTL_S = 3600
DRY_RUN = os.getenv("FIXER_DRY_RUN", "false").lower() == "true"  # make and test fixes, but open no pull request

HELP = (
    "I'm the **AgentReady Fixer**. I change your store's code so AI shopping agents can find, compare, add to cart "
    "and hand your customers a checkout link, and I prove it with a before/after shopping test.\n\n"
    "Send me your site and its GitHub repo, for example:\n"
    "- `Fix voltkart.onrender.com, code at github.com/you/your-store`\n"
    "- `Fix github.com/you/your-store for wireless earbuds under ₹10,000`\n\n"
    "I reply with a fix plan; you choose what to apply. Then I open a pull request. Nothing goes live until you merge it."
)

_jobs: dict[str, fixer.Job] = {}
_busy = asyncio.Lock()   # one store build at a time on this machine


def message(text: str, end: bool = True) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(content=content)


def _task_from(text: str) -> str:
    t = re.sub(r"https?://\S+|(?:[\w-]+\.)+[a-z]{2,}\S*", " ", text, flags=re.I)
    t = re.sub(r"\b(fix|please|my|store|site|website|shop|code|repo|is|at|on|in|for|the|and|it|github)\b", " ", t, flags=re.I)
    t = " ".join(t.replace(",", " ").split()).strip(" :-.?")
    return t if re.search(r"[a-z]{3,}", t, re.I) else "any product"


def _site_from(text: str) -> str | None:
    for m in URL_RE.finditer(text):
        if "github.com" not in m.group(1).lower():
            return m.group(1).rstrip(".,;:!?)")
    return None


chat = Protocol(spec=chat_protocol_spec)


@chat.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))
    text = " ".join(i.text for i in msg.content if isinstance(i, TextContent)).strip()
    if not text:
        return
    job = _jobs.get(sender)
    if job and time.time() - job.created > JOB_TTL_S:
        fixer.cleanup(job)
        _jobs.pop(sender, None)
        job = None

    if re.match(r"\s*apply\b", text, re.I):
        if not job:
            await ctx.send(sender, message("There's no fix plan waiting. Send me your site and GitHub repo first.\n\n" + HELP))
            return
        fixes = fixer.pick(job, text)
        if not fixes:
            await ctx.send(sender, message(f"Which fixes? Reply **apply all** or numbers from the plan, e.g. **apply 1,2** (1 to {len(job.plan.fixes)})."))
            return
        await ctx.send(sender, message(
            f"On it: {len(fixes)} fix{'es' if len(fixes) > 1 else ''} for {job.repo.full}. I'll install and test your store before and "
            "after the change. This usually takes 5 to 15 minutes; I'll message you when the pull request is ready.", end=False))
        asyncio.create_task(_apply(ctx, sender, job, fixes))
        return

    if re.match(r"\s*re-?test\b", text, re.I):
        site = _site_from(text) or (job.site if job else None)
        if not site:
            await ctx.send(sender, message("Which site should I retest? e.g. `retest voltkart.onrender.com`"))
            return
        report = await shop(site, job.task if job else _task_from(text))
        await ctx.send(sender, message(format_report(report)))
        return

    repo_ref = github.parse_repo(text)
    if not repo_ref:
        await ctx.send(sender, message(HELP))
        return
    owner, name = repo_ref
    if not github.allowed(owner, name):
        await ctx.send(sender, message(
            f"github.com/{owner}/{name} isn't connected to AgentReady yet, so I can't change its code. "
            "Ask the AgentReady team to connect it, or try one of our demo stores."))
        return
    try:
        repo = await github.get_repo(owner, name)
    except github.GitHubError as err:
        await ctx.send(sender, message(str(err)))
        return
    site = _site_from(text) or repo.homepage
    if not site:
        await ctx.send(sender, message(f"What's the live address of the store in {repo.full}? e.g. `Fix mystore.com, code at {repo.url}`"))
        return
    task = _task_from(text)
    await ctx.send(sender, message(f"Reading {repo.full} and testing {site} like an AI shopper (“{task}”). About a minute…", end=False))
    try:
        new = await fixer.diagnose(site, owner, name, task)
    except Exception as err:
        ctx.logger.exception("Diagnose failed")
        await ctx.send(sender, message(f"Sorry, I couldn't prepare a fix plan: {err}"))
        return
    if job:
        fixer.cleanup(job)
    _jobs[sender] = new
    await ctx.send(sender, message(new.live_text + "\n\n---\n\n" + fixer.plan_text(new)))


async def _apply(ctx: Context, sender: str, job: fixer.Job, fixes):
    async def progress(step: str):
        ctx.logger.info(f"[{job.repo.full}] {step}")

    try:
        async with _busy:
            res = await fixer.apply(job, fixes, progress, open_pr=not DRY_RUN)
    except Exception as err:
        ctx.logger.exception("Apply failed")
        await ctx.send(sender, message(f"Sorry, fixing {job.repo.full} failed unexpectedly ({type(err).__name__}: {err})."))
        return
    finally:
        _jobs.pop(sender, None)
        fixer.cleanup(job)
    lines = [f"## {'✅ Pull request ready' if res.pr_url else '⚠️ No pull request'}: {job.repo.full}", ""]
    if res.before and res.after:
        lines += [f"**AI shopping test: {res.before['passed']}/5 → {res.after['passed']}/5**", "", "| Step | Before | After |", "|---|---|---|"]
        lines += [f"| {b['name']} | {'✅' if b['passed'] else '❌'} | {'✅' if a['passed'] else '❌'} |"
                  for b, a in zip(res.before["steps"], res.after["steps"])]
        lines.append("")
    if res.message:
        lines += [res.message, ""]
    if res.summary:
        lines += ["**What I changed**", res.summary, ""]
    if res.pr_url:
        lines += [f"Review it here: {res.pr_url}", "",
                  f"Once it's merged and deployed, send **retest** and I'll check {job.site} live."]
    await ctx.send(sender, message("\n".join(lines)))


@chat.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


def create_agent(mailbox: bool | None = None, port: int | None = None) -> Agent:
    seed = os.getenv("FIXER_AGENT_SEED")
    if not seed:
        raise RuntimeError("Set FIXER_AGENT_SEED in agents/.env (any long secret phrase).")
    if mailbox is None:
        mailbox = os.getenv("AGENT_MAILBOX", "false").lower() == "true"
    port = port or int(os.getenv("FIXER_PORT", "8003"))
    kwargs = dict(name="AgentReady Fixer", seed=seed, port=port)
    if mailbox:
        kwargs.update(mailbox=True, publish_agent_details=True, description=PROFILE_DESCRIPTION)
    else:
        kwargs.update(endpoint=[f"http://127.0.0.1:{port}/submit"])
    agent = Agent(**kwargs)
    # Read as UTF-8: uAgents' own readme_path uses the platform encoding, which breaks on ₹ on Windows.
    agent._readme = (ROOT / "profiles" / PROFILE_README).read_text(encoding="utf-8")
    agent.include(chat, publish_manifest=mailbox)
    return agent


if __name__ == "__main__":
    create_agent().run()
