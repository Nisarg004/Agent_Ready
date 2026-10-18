# AgentReady agents (Fetch.ai)

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

Fetch.ai uAgents for AgentReady, built for Fetch-A-Thon 3.0. They speak the
Agent Chat Protocol, so they can be used from ASI:One.

| Agent | What it does | Address |
|---|---|---|
| **AgentReady** | Scans a website and explains how well AI shopping agents can find, read and buy from it | `agent1qwl5c4d77prydcy4skseaktuwquy6qwdp68fv5fqrkdgfvx3ph9uc6w8a2v` (local dev seed) |

Coming next: "What AI sees", agent-access settings, auto-fix Pull Requests, and a Shopper agent that proves the fixes work.

## Run it locally

Requires Python 3.10+.

```bash
cd agents
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
```

Fill in `.env`: set `AGENTREADY_AGENT_SEED` to any long secret phrase, and `ASI1_API_KEY` to your key from [asi1.ai](https://asi1.ai/dashboard/api-keys). Without the key the agent still works, using simple address detection.

**Try a conversation without ASI:One** (runs the agent and a test client together):

```bash
python tools/local_chat_test.py "Is example.com ready for AI shoppers?"
```

**Run the agent on its own:**

```bash
python agentready_agent/agent.py
```

## Connect to Agentverse and ASI:One

1. In `.env` set `AGENT_MAILBOX=true`, then run the agent.
2. Open the **Agent inspector** link it prints and click **Connect → Mailbox**.
3. On Agentverse, set the name, handle and description, then use **Chat with Agent**.

## Files

| Path | Purpose |
|---|---|
| `agentready_agent/agent.py` | uAgent + chat protocol wiring, per-user scan limit |
| `agentready_agent/brain.py` | Understands the message (ASI:One `asi1` model, regex fallback), calls the AgentReady API, writes the reply |
| `tools/local_chat_test.py` | Local end-to-end chat test |

The agent sends `AGENT_API_KEY` to the AgentReady API so all its users don't share one IP's public scan limit. Set the same value as `AGENT_API_KEY` on the API.
