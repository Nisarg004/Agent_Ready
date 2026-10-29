"""Which language model the agents think with: NVIDIA Nemotron on Nebius Token Factory.

Both model users go through here: AgentReady reads intent from chat messages with a
fast Nemotron model, and the Fixer drives its tool-calling coding loop with a larger
one. Token Factory speaks the OpenAI API, so the rest of the code doesn't change.

With NEBIUS_API_KEY set, Nebius is used. Without it, ASI:One (ASI1_API_KEY) is the
fallback, so an agent that hasn't been given a Nebius key keeps working as before.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from openai import AsyncOpenAI

NEBIUS_BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
ASI1_BASE_URL = "https://api.asi1.ai/v1"

# Fast everyday calls (reading a chat message) and serious reasoning (editing a repo).
# Exact ids are listed by: python tools/list_models.py
NEBIUS_CHAT_MODEL = os.getenv("NEBIUS_CHAT_MODEL", "nvidia/NVIDIA-Nemotron-Nano-9B-v2")
NEBIUS_CODER_MODEL = os.getenv("NEBIUS_CODER_MODEL", "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5")


@dataclass
class Model:
    provider: str  # "nebius" | "asi1"
    client: AsyncOpenAI
    name: str

    @property
    def label(self) -> str:
        return f"Nemotron on Nebius ({self.name})" if self.provider == "nebius" else f"ASI:One ({self.name})"


def _pick(nebius_model: str, asi1_model: str, timeout: float | None) -> Model | None:
    opts = {"timeout": timeout} if timeout else {}
    if key := os.getenv("NEBIUS_API_KEY", ""):
        return Model("nebius", AsyncOpenAI(base_url=NEBIUS_BASE_URL, api_key=key, **opts), nebius_model)
    if key := os.getenv("ASI1_API_KEY", ""):
        return Model("asi1", AsyncOpenAI(base_url=ASI1_BASE_URL, api_key=key, **opts), asi1_model)
    return None


def chat_model() -> Model | None:
    """For short calls such as reading a chat message. None means no key: callers fall back to rules."""
    return _pick(NEBIUS_CHAT_MODEL, os.getenv("ASI1_MODEL", "asi1"), None)


def coder_model() -> Model | None:
    """For the Fixer's coding loop."""
    return _pick(NEBIUS_CODER_MODEL, os.getenv("FIXER_MODEL", "asi1"), 120)
