---
name: ngrok-setup
description: Set up ngrok for the user’s task, including connecting an AI client to ngrok’s hosted MCP server or configuring the CLI, SDK, REST API, Terraform, or Kubernetes Operator. Use for "set up ngrok", "set up ngrok MCP", "connect ngrok to my agent", authtoken setup, or authentication errors. For exposing the user’s own MCP server, use run-mcp-gateway.
license: MIT
metadata:
  author: ngrok
  version: "1.0"
  category: setup
  surface: job
compatibility: Requires access to the chosen client or ngrok surface; the CLI is not required to connect the hosted MCP server.
---

# Set up ngrok

Match setup to the user's goal. Check what already works, then complete the missing steps. The CLI, skills, and hosted MCP can be installed independently.

## 1. Choose the path

| User's goal | Path |
| --- | --- |
| Connect an AI client to ngrok's MCP server for live account data or account changes | Hosted MCP below |
| Put an MCP server they're building online with ngrok | `run-mcp-gateway` |
| Expose a local service or start an endpoint from this machine | Agent CLI or SDK below |
| Manage resources through Terraform, Kubernetes, or a control plane | API key below; see `ngrok-surfaces` |

If the request is just "set up ngrok" and the goal is unclear, briefly distinguish local tunnels, reusable skills, and account access through MCP. If the user asks specifically for ngrok MCP, start with the hosted MCP path.

## 2. Set up the chosen path

**Hosted ngrok MCP:** Check whether the current AI client already has ngrok connected and its tools available. If not, read the current [ngrok MCP quickstart](https://ngrok.com/docs/mcp-server), identify the client and the machine or cloud environment that runs it, and follow that client's instructions for `https://mcp.ngrok.com/mcp`. Run setup commands you can perform; the user completes browser sign-in and consent. If the client cannot use OAuth, follow the quickstart's personal access token (PAT) path and have the user configure the token in the client's secret storage. An agent authtoken or API key will not authenticate the hosted MCP. Verify that the client sees ngrok tools and can identify the signed-in account. MCP tools can change account resources under the user's permissions; preserve the client's approval prompts.

**Agent CLI or SDK (authtoken):**
1. Check whether the CLI or project SDK is installed and configured. For the CLI, run `ngrok config check` and check whether `NGROK_AUTHTOKEN` is set without printing its value.
2. If an authtoken is missing, have the user get it from [Your Authtoken](https://dashboard.ngrok.com/get-started/your-authtoken) and run `ngrok config add-authtoken <YOUR_TOKEN>` themselves. On a headless host, they can set `NGROK_AUTHTOKEN` through their secret store. Do not ask them to paste it into chat.
3. Recheck the configuration, then return to the requested task. See `ngrok-surfaces` for SDK-specific setup.

**Terraform, Kubernetes Operator, or REST API (API key):** These surfaces use an [API key](https://dashboard.ngrok.com/api-keys); the Operator also needs an authtoken. Have the user configure the credential in the provider, Operator, or `NGROK_API_KEY`, without pasting it into chat. Use `ngrok-surfaces` for the chosen surface and confirm access with a read before making changes.

## 3. Offer adjacent capabilities when useful

For a broad request such as "set up ngrok for my coding agent", explain this optional sequence and skip what already works:

1. Install and authenticate the ngrok CLI if the agent needs to start local tunnels or endpoints.
2. [Install ngrok skills](https://ngrok.com/docs/for-agents/skills) if the user wants reusable guidance for exposing, securing, and troubleshooting services.
3. Connect the hosted MCP if the agent needs live account context or account-side actions.

If the user requested just one capability, complete that first. Then return to the user's original task.

## Notes for agents

- Never ask for or echo an authtoken, API key, PAT, or secret in chat. If one appears, do not repeat it; suggest rotation.
- When authentication fails, identify the chosen surface and credential before changing configuration or rotating a token.
