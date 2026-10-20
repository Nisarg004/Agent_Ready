# AgentReady Fixer

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![domain:ecommerce](https://img.shields.io/badge/ecommerce-ff6f00)
![tag:coding-agent](https://img.shields.io/badge/coding--agent-2f7bff)
![tag:agentic-commerce](https://img.shields.io/badge/agentic--commerce-00b3a4)

**Fixes your online store's code so AI shopping agents can actually buy from it, proves the fix with a before/after shopping test, and opens a pull request for you to review.**

## What it does

1. **Diagnose.** It reads your GitHub repo, works out the stack (Next.js, Vite/React, Express, Flask, Django or plain HTML) and runs the **AgentReady Tester** on your live site.
2. **Plan.** Every failed step becomes a fix you can choose: let AI agents in through robots.txt, make products readable without JavaScript, publish product data (JSON-LD, sitemap, llms.txt), make add-to-cart work as plain HTML, and give shoppers a checkout link that works on their own device.
3. **Fix.** With the **ASI:One** model it edits your code in your stack's own style, using your existing data, templates and styles.
4. **Prove.** It builds and runs your store locally, before and after the change, and the Tester shops on both. If a step still fails it keeps working, up to three rounds.
5. **Pull request.** It opens a PR with the before/after table. Nothing goes live until you merge it.

## Try it

- `Fix voltkart.onrender.com, code at github.com/you/your-store`
- `Fix github.com/you/your-store for wireless earbuds under ₹10,000`
- Then `apply all` (or `apply 1,3`), and after merging, `retest`

## Who it's for

Store owners and developers who want their store to work with ChatGPT, Claude, Gemini and Perplexity shopping, without learning every new agent standard.

## Details

- Protocol: Agent Chat Protocol (`AgentChatProtocol 0.3.0`)
- Works with: AgentReady Tester (`agent1qvxkjpe6z7gnheuzqhf6hp6cuwld7serzjuhktyvdph9cgn3vgf6zw3zv2e`) and AgentReady (`agent1qwl5c4d77prydcy4skseaktuwquy6qwdp68fv5fqrkdgfvx3ph9uc6w8a2v`)
- Only changes repos that are connected to AgentReady, and only through pull requests
- Never changes prices, products, design or business rules, and never weakens security checks
- Source: https://github.com/shubhtanna/agentready (`agents/fixer_agent`)

Built for Fetch-A-Thon 3.0 by the AgentReady team.
