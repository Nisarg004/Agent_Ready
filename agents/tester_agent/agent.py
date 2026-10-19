"""AgentReady Tester as a Fetch.ai uAgent speaking the Agent Chat Protocol.

Message it a website and a shopping task, e.g.
    "Can an AI agent buy running shoes under ₹10,000 on stride-lab-beta.vercel.app?"
It tries to do it and replies with a step-by-step pass/fail report.

Run it:   python tester_agent/agent.py
Settings: agents/.env (TESTER_AGENT_SEED, AGENT_MAILBOX, TESTER_PORT).
"""

from __future__ import annotations

import os
import re
import sys
import time
from collections import defaultdict, deque
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

from tester_agent.shopper import format_report, run  # noqa: E402

TESTS_PER_HOUR = int(os.getenv("TESTER_RUNS_PER_USER_PER_HOUR", "6"))
_recent: dict[str, deque[float]] = defaultdict(deque)

URL_RE = re.compile(r"(https?://[^\s<>\"']+|(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>\"']*)?)", re.I)

HELP = (
    "I'm the **AgentReady Tester**. I check whether an AI shopping agent can actually buy from a website: "
    "find a product, compare options, add it to the cart and hand you a checkout link.\n\n"
    "Send me a site and what to shop for, for example:\n"
    "- `Can an AI agent buy running shoes under ₹10,000 on stride-lab-beta.vercel.app?`\n"
    "- `Test nest-and-grain.vercel.app: a dining chair under ₹10,000`"
)


def _allow(sender: str) -> bool:
    now, q = time.time(), _recent[sender]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= TESTS_PER_HOUR:
        return False
    q.append(now)
    return True


def split_request(text: str) -> tuple[str | None, str]:
    """Pull the website out of the message; the rest is the shopping task."""
    m = URL_RE.search(text)
    if not m:
        return None, text
    site = m.group(1).rstrip(".,;:!?)")
    task = (text[: m.start()] + " " + text[m.end():]).strip()
    task = re.sub(r"^(test|check|try|can an ai agent|can ai agents?|on|at|:|-)\s+", "", task, flags=re.I)
    task = re.sub(r"^(buy|find|get|shop for|order)\s+", "", task.strip(), flags=re.I)
    task = re.sub(r"\s+(on|at|from|in)\s*$", "", task.strip(" :-?"), flags=re.I).strip(" :-?")
    return site, task or "any product"


def reply(text: str) -> ChatMessage:
    return ChatMessage(content=[TextContent(type="text", text=text), EndSessionContent(type="end-session")])


chat = Protocol(spec=chat_protocol_spec)


@chat.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))
    text = " ".join(i.text for i in msg.content if isinstance(i, TextContent)).strip()
    if not text:
        return
    site, task = split_request(text)
    if not site:
        await ctx.send(sender, reply(HELP))
        return
    if not _allow(sender):
        await ctx.send(sender, reply(f"You've run {TESTS_PER_HOUR} tests in the last hour. Please try again later."))
        return
    ctx.logger.info(f"Testing {site} for {sender[:16]}…: {task!r}")
    try:
        report = await run(site, task)
        await ctx.send(sender, reply(format_report(report)))
    except Exception as err:  # never leave the user without an answer
        ctx.logger.exception("Tester run failed")
        await ctx.send(sender, reply(f"Sorry, the test on {site} failed unexpectedly ({type(err).__name__}). Please try again."))


@chat.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


def create_agent(mailbox: bool | None = None, port: int | None = None) -> Agent:
    seed = os.getenv("TESTER_AGENT_SEED")
    if not seed:
        raise RuntimeError("Set TESTER_AGENT_SEED in agents/.env (any long secret phrase).")
    if mailbox is None:
        mailbox = os.getenv("AGENT_MAILBOX", "false").lower() == "true"
    port = port or int(os.getenv("TESTER_PORT", "8002"))
    kwargs = dict(name="AgentReady Tester", seed=seed, port=port)
    if mailbox:
        kwargs.update(mailbox=True, publish_agent_details=True)
    else:
        kwargs.update(endpoint=[f"http://127.0.0.1:{port}/submit"])
    agent = Agent(**kwargs)
    agent.include(chat, publish_manifest=mailbox)
    return agent


if __name__ == "__main__":
    create_agent().run()
