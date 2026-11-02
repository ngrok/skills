---
name: ngrok-setup
description: Set up ngrok for the user's task, including connecting an AI client to ngrok's hosted MCP server or configuring the CLI, SDK, REST API, Terraform, or Kubernetes Operator. Use for "set up ngrok", "set up ngrok MCP", "connect ngrok to my agent", authtoken setup, or auth and configuration errors. For exposing the user's own MCP server, use run-mcp-gateway.
license: MIT
metadata:
  author: ngrok
  version: "1.0"
  category: setup
  surface: job
compatibility: Requires access to the chosen AI client or ngrok surface; the CLI is not required to connect the hosted MCP server.
---

# Set up ngrok

Set up the surface the user needs for the task. Check what is already working, then complete only the missing steps. An agent authtoken, an API key, and a hosted MCP connection serve different purposes.

## 1. Choose the path

| User's goal | Path |
| --- | --- |
| Connect an AI client to ngrok's own MCP server for live account data or account changes | Hosted MCP below |
| Put an MCP server they are building online with ngrok | `run-mcp-gateway` |
| Expose a local service or start an endpoint from this machine | Agent CLI or SDK below |
| Manage resources from Terraform, Kubernetes, or a controlplane | API key below; see `ngrok-surfaces` |

Infer the path from the request and project. If "set up ngrok" has no clearer goal, briefly offer local tunnels, agent skills, and hosted MCP as options. Do not treat them as prerequisites for one another.

## 2. Set up the selected path

**Hosted MCP (OAuth for supported clients):** Check whether the current AI client already has ngrok connected and its tools available. If not, read the current [ngrok MCP quickstart](https://ngrok.com/docs/mcp-server), identify the client and the machine or cloud environment that runs it, then follow that client's instructions for `https://mcp.ngrok.com/mcp`. Run setup steps you can perform; the user completes browser sign-in and consent. Never substitute a CLI authtoken or API key for MCP authentication. If the client cannot use OAuth, follow the quickstart's personal access token (PAT) path and have the user put the PAT in the client's secret storage, never in chat. The server is invite-only; if access is denied after sign-in, point the user to the [access request](https://dashboard.ngrok.com/early-access#mcp-server). Verify that the client sees ngrok tools and can identify the signed-in account. The MCP can make account changes under the user's permissions, so preserve the client's approval prompts.

**Agent CLI or SDK (authtoken):** Check whether the CLI or project SDK is present and configured. For the CLI, run `ngrok config check` and check whether `NGROK_AUTHTOKEN` is set without printing its value. If an authtoken is missing, send the user to [Your Authtoken](https://dashboard.ngrok.com/get-started/your-authtoken) and have them run `ngrok config add-authtoken <YOUR_TOKEN>` themselves. On a headless host, they can set `NGROK_AUTHTOKEN` through their secret store. Do not ask them to paste it into chat. Recheck the configuration, then return to the requested task. Use `ngrok-surfaces` for SDK-specific setup.

**Terraform, Kubernetes Operator, or REST API (API key):** These surfaces use an [API key](https://dashboard.ngrok.com/api-keys); the Operator also needs an authtoken. Have the user configure the credential in the provider, Operator, or `NGROK_API_KEY`, without pasting it into chat. Use `ngrok-surfaces` for the chosen surface and confirm access with a read before making changes.

## 3. Offer the other capabilities when useful

For a broad request such as "set up ngrok for my coding agent", explain the optional sequence and skip what is already working:

1. Install and authenticate the ngrok CLI if the agent needs to start local tunnels or endpoints.
2. [Install ngrok skills](https://ngrok.com/docs/for-agents/skills) if the user wants reusable task guidance for exposing, securing, and troubleshooting services.
3. Connect the hosted MCP if the agent needs live account context or account-side actions.

The CLI, skills, and MCP can be installed independently. If the user asked for just one, complete that one first; offer the others only when they help with the user's goal.

## Notes for agents

- Never ask for or echo an authtoken, API key, PAT, or secret in chat. If one appears, do not repeat it; suggest rotation.
- When authentication fails, identify the selected surface and its credential before changing configuration or rotating a token.
