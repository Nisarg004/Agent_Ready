"""AgentReady as a Fetch.ai uAgent speaking the Agent Chat Protocol.

Run it:   python agentready_agent/agent.py
Settings: agents/.env (see .env.example). With AGENT_MAILBOX=true the agent
connects to Agentverse so ASI:One can reach it; with false it stays local.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from uagents import Agent, Context, Protocol  # noqa: E402
from uagents_core.contrib.protocols.chat import (  # noqa: E402
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

import brain  # noqa: E402

# Our API lets this agent skip its per-IP limit, so the agent limits each
# chat user instead. In memory is enough: a restart forgiving everyone is fine.
SCANS_PER_HOUR = int(os.getenv("AGENT_SCANS_PER_USER_PER_HOUR", "10"))
# The AgentReady Tester agent we ask to try shopping on each site.
TESTER_ADDRESS = os.getenv("TESTER_AGENT_ADDRESS", "").strip()
TESTER_TIMEOUT_S = int(os.getenv("TESTER_TIMEOUT_S", "150"))
_recent: dict[str, deque[float]] = defaultdict(deque)


def _allow(sender: str) -> bool:
    now = time.time()
    q = _recent[sender]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= SCANS_PER_HOUR:
        return False
    q.append(now)
    return True


def text_message(text: str, end_session: bool = True) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(content=content)


chat = Protocol(spec=chat_protocol_spec)


@chat.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    # Acknowledge first, always: ASI:One waits for it before showing progress.
    await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))

    text = " ".join(item.text for item in msg.content if isinstance(item, TextContent)).strip()
    if any(isinstance(item, StartSessionContent) for item in msg.content) and not text:
        return
    if not text:
        return

    if TESTER_ADDRESS and sender == TESTER_ADDRESS:
        return  # a late Tester report: already handled (or timed out) inside ask_tester

    ctx.logger.info(f"Message from {sender[:16]}…: {text[:120]!r}")

    intent = await brain.understand(text)
    if intent.action == "scan" and not _allow(sender):
        await ctx.send(
            sender,
            text_message(f"You've run {SCANS_PER_HOUR} scans in the last hour. Please try again a little later."),
        )
        return

    if intent.action != "scan" or not intent.url:
        await ctx.send(sender, text_message(brain.HELP_TEXT))
        return

    # Two things at once: our scanner grades the site, and the Tester agent
    # actually tries to shop on it. The owner gets both in one answer.
    (scan_reply, scan_id), tester_reply = await asyncio.gather(
        brain.reply_to(text, intent),
        ask_tester(ctx, intent.url, intent.shopping),
    )
    if scan_id:
        # Remembered per user so later steps (fixes, re-scan) know which scan
        # "my site" refers to.
        ctx.storage.set(f"last_scan:{sender}", scan_id)
    await ctx.send(sender, text_message(combine(scan_reply, tester_reply)))


async def ask_tester(ctx: Context, url: str, shopping: str | None) -> str | None:
    """Ask the AgentReady Tester agent to try shopping on the site. Returns its report text."""
    if not TESTER_ADDRESS:
        return None
    request = f"{shopping or 'any product'} on {url}"
    ctx.logger.info(f"Asking Tester: {request!r}")
    try:
        reply, status = await ctx.send_and_receive(
            TESTER_ADDRESS,
            ChatMessage(content=[TextContent(type="text", text=request)]),
            response_type=ChatMessage,
            timeout=TESTER_TIMEOUT_S,
        )
    except Exception:
        ctx.logger.exception("Tester request failed")
        return None
    if not isinstance(reply, ChatMessage):
        ctx.logger.warning(f"No report from Tester: {getattr(status, 'detail', status)}")
        return None
    return " ".join(i.text for i in reply.content if isinstance(i, TextContent)).strip() or None


def combine(scan_reply: str, tester_reply: str | None) -> str:
    if not tester_reply:
        return scan_reply + "\n\n_The shopping test by the AgentReady Tester agent didn't finish in time, so only the scan is shown._"
    return (
        "# Part 1: AI readiness scan\n\n" + scan_reply
        + "\n\n---\n\n# Part 2: Can an AI agent actually buy here?\n"
        + "_Our Tester agent just tried it, step by step:_\n\n" + tester_reply
    )


@chat.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


def create_agent(mailbox: bool | None = None, port: int | None = None) -> Agent:
    seed = os.getenv("AGENTREADY_AGENT_SEED")
    if not seed:
        raise RuntimeError("Set AGENTREADY_AGENT_SEED in agents/.env (any long secret phrase).")
    if mailbox is None:
        mailbox = os.getenv("AGENT_MAILBOX", "false").lower() == "true"
    port = port or int(os.getenv("PORT", "8001"))

    kwargs = dict(name="AgentReady", seed=seed, port=port)
    if mailbox:
        kwargs.update(mailbox=True, publish_agent_details=True)
    else:
        kwargs.update(endpoint=[f"http://127.0.0.1:{port}/submit"])

    agent = Agent(**kwargs)
    # publish_manifest lets Agentverse and ASI:One see that we speak the chat protocol.
    agent.include(chat, publish_manifest=mailbox)
    return agent


if __name__ == "__main__":
    create_agent().run()
