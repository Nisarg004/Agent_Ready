# AgentReady

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![domain:ecommerce](https://img.shields.io/badge/ecommerce-ff6f00)
![tag:website-audit](https://img.shields.io/badge/website--audit-2f7bff)
![tag:agentic-commerce](https://img.shields.io/badge/agentic--commerce-00b3a4)

**Checks whether AI shopping agents (ChatGPT, Claude, Gemini, Perplexity) can find, read and buy from your online store, and shows what to fix.**

## What it does

Send AgentReady a website. In one reply you get two things:

1. **AI readiness scan.** A 0–100 score and letter grade from seven checks: AI bot access in robots.txt, structured product data, content an agent can read without JavaScript, crawlability, page structure, trust pages and agent checkout support. The most important fixes come first, with a link to the full report and ready-to-paste code.
2. **A live shopping test.** AgentReady asks the **AgentReady Tester** agent to actually try to shop on the site: reach it, find products, compare two, add one to the cart, and get a checkout link the shopper can open. Each step passes or fails with the reason.

The scan tells you *why*; the shopping test shows *what really happens* when an AI agent tries to buy from you.

## Try it

- `Is mystore.com ready for AI shoppers?`
- `Can AI agents buy wireless earbuds under ₹10,000 on voltkart.onrender.com?`
- `Check nest-and-grain.vercel.app`

If you name a product or budget, the shopping test looks for that; otherwise it tries any product.

## How it works

- Understands your request with the **ASI:One** model (`asi1`).
- Scans the site with the AgentReady API. If the site is asleep or returning server errors, it waits for it to wake and scans again, so an outage isn't graded as a broken site.
- Messages the **AgentReady Tester** agent over the Agent Chat Protocol and merges both results into one answer.

## Who it's for

Online store owners, D2C brands, agencies and developers who want their store to work with AI shopping assistants.

## Details

- Protocol: Agent Chat Protocol (`AgentChatProtocol 0.3.0`)
- Works with: AgentReady Tester (`agent1qvxkjpe6z7gnheuzqhf6hp6cuwld7serzjuhktyvdph9cgn3vgf6zw3zv2e`)
- Limit: 25 checks per user per hour
- Source: https://github.com/shubhtanna/agentready (`agents/agentready_agent`)
- Web app: https://agentready-five-rust.vercel.app

Built for Fetch-A-Thon 3.0 by the AgentReady team.
