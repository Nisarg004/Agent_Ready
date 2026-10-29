"""Check the Nebius key and list the NVIDIA models Token Factory offers it.

    python tools/list_models.py           # Nemotron and other NVIDIA models
    python tools/list_models.py --all     # every model
    python tools/list_models.py --ping    # also send one short message to each configured model

Copy the ids you want into NEBIUS_CHAT_MODEL and NEBIUS_CODER_MODEL in agents/.env.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from shared import llm  # noqa: E402


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true")
    p.add_argument("--ping", action="store_true")
    a = p.parse_args()

    chat, coder = llm.chat_model(), llm.coder_model()
    if not chat or chat.provider != "nebius":
        sys.exit("NEBIUS_API_KEY is not set in agents/.env")

    ids = sorted(m.id async for m in chat.client.models.list())
    shown = ids if a.all else [i for i in ids if "nvidia" in i.lower() or "nemotron" in i.lower()]
    print(f"{len(shown)} of {len(ids)} models:")
    for i in shown:
        print("  " + i)

    for role, m in (("chat", chat), ("coder", coder)):
        mark = "ok" if m.name in ids else "NOT OFFERED, pick one from the list"
        print(f"\n{role}: {m.name} ({mark})")
        if a.ping and m.name in ids:
            r = await m.client.chat.completions.create(model=m.name, max_tokens=200,
                                                       messages=[{"role": "user", "content": "Reply with the word ready."}])
            print("  reply: " + (r.choices[0].message.content or "").strip()[:200])


if __name__ == "__main__":
    asyncio.run(main())
