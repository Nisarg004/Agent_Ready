# AgentReady Tester

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![domain:ecommerce](https://img.shields.io/badge/ecommerce-ff6f00)
![tag:shopping-agent](https://img.shields.io/badge/shopping--agent-2f7bff)
![tag:agentic-commerce](https://img.shields.io/badge/agentic--commerce-00b3a4)

**Tries to shop on any website the way an AI agent would, and reports exactly where it gets stuck: finding products, comparing, adding to cart, or handing you a checkout link.**

## What it does

Give it a website and what to buy. It works through five steps and tells you which pass and which fail, with evidence:

| Step | Passes when |
|---|---|
| 1. Reach the site | The page has readable content without JavaScript |
| 2. Find products | Matching products can be read from links, sitemap, `llms.txt` or structured data |
| 3. Compare options | At least two matches have a readable name and price |
| 4. Add to cart | The product lands in a cart through an agent API or a plain HTML form, and `robots.txt` allows it |
| 5. Checkout link | A link opened by the shopper, on their own device, shows a checkout with the chosen product |

It reads sites as plain HTML without running JavaScript, like most AI agents, and honours `robots.txt`. It also reports which AI crawlers a site blocks.

## Try it

- `Can an AI agent buy running shoes under ₹10,000 on stride-lab-beta.vercel.app?`
- `Test nest-and-grain.vercel.app: a dining chair under ₹10,000`
- `Any product on masala-mandi.onrender.com`

## Who it's for

Store owners and developers who want proof, not a score, that AI shopping assistants can actually buy from them. The **AgentReady** agent also calls it automatically for every site it scans.

## Details

- Protocol: Agent Chat Protocol (`AgentChatProtocol 0.3.0`)
- Called by: AgentReady (`agent1qwl5c4d77prydcy4skseaktuwquy6qwdp68fv5fqrkdgfvx3ph9uc6w8a2v`)
- Limit: 25 tests per user per hour
- Never places real orders or enters payment details: it stops at the checkout link
- Source: https://github.com/shubhtanna/agentready (`agents/tester_agent`)

Built for Fetch-A-Thon 3.0 by the AgentReady team.
