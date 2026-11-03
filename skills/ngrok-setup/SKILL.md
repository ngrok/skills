---
name: ngrok-setup
description: Set up and authenticate ngrok on the surface the user's task needs, including the ngrok CLI, an SDK, the REST API, infrastructure as code (Terraform or Kubernetes Operator), or ngrok's hosted MCP server. Detect what is already configured and choose the right surface or combination. Use before other ngrok tasks when setup is missing, whenever an ngrok command fails with an authentication or configuration error, or for "set up ngrok", "install ngrok", "add my authtoken", "ngrok isn't authenticated", "getting an auth error from ngrok", "set up ngrok MCP", "connect ngrok to my agent", or "connect the ngrok MCP server". For the user's own MCP server, use run-mcp-gateway.
license: MIT
metadata:
  author: ngrok
  version: "1.0"
  category: setup
  surface: job
compatibility: Requires the ngrok CLI, an ngrok SDK, an API key, or an MCP-capable AI client, depending on the chosen surface.
---

# Set up ngrok

Get the user authenticated and ready to work on the right ngrok surface. Starting a tunnel or accessing account resources requires authentication with the credential for that surface; this helps prevent abuse. Check what's already installed and configured, then complete only the missing steps. The ngrok CLI, skills, and hosted MCP can be set up independently.

## 1. Figure out the surface

Infer the user's goal and desired outcome from the request and project, then choose the surface or combination of surfaces that fits. Read `ngrok-surfaces` for the full routing guidance and mechanics for the ngrok CLI, SDKs, REST API, and infrastructure as code. The table below highlights common setup requests; it is not exhaustive.

| User's goal | Surface or skill |
| --- | --- |
| Connect an AI client to ngrok's hosted MCP server for account data or actions | Hosted MCP below |
| Put an MCP server they're building online with ngrok | `run-mcp-gateway` |
| Start a local tunnel or endpoint from this machine | ngrok CLI, or an SDK if the app owns its lifetime |
| Provision account resources through Terraform, Kubernetes, or a control plane | Terraform provider, Kubernetes Operator, or REST API; see `ngrok-surfaces` |

If no stronger signal points elsewhere, use the ngrok CLI as the default for a one-off task. An explicit "set up ngrok MCP" request goes straight to hosted MCP setup. Some tasks use more than one surface, such as provisioning a cloud endpoint and starting a local agent.

## 2. Authenticate and prepare the chosen surface

**Hosted ngrok MCP (OAuth or PAT):** The server is available on all plans, including free. Check whether the AI client already has ngrok connected and its tools available. If not, read the current [ngrok MCP quickstart](https://ngrok.com/docs/mcp-server), identify the client and where it runs, and follow that client's instructions for `https://mcp.ngrok.com/mcp`. Run the setup steps you can perform; the user completes browser sign-in and consent. If the client cannot use OAuth, follow the quickstart's personal access token (PAT) path and have the user configure it in the client's secret storage. An agent authtoken or API key will not authenticate the hosted MCP. Verify that the client sees ngrok tools and identifies the signed-in account; use `platform_whoami` when available. MCP tools can change account resources under the user's permissions, so preserve the client's approval prompts.

**ngrok CLI or SDK (agent authtoken):**
1. Check that the ngrok CLI or project SDK is installed. If the CLI is missing, install it for the user's platform (for example, `brew install ngrok` on macOS), then confirm with `ngrok --help`. For an SDK, confirm the ngrok dependency is in the project; see `ngrok-surfaces`.
2. For the ngrok CLI, run `ngrok config check` and check whether `NGROK_AUTHTOKEN` is set without printing its value. Check the SDK's configured authtoken as appropriate.
3. If an authtoken is missing, have the user get it from [Your Authtoken](https://dashboard.ngrok.com/get-started/your-authtoken) and run `ngrok config add-authtoken <YOUR_TOKEN>` themselves, or set `NGROK_AUTHTOKEN` through their secret store on a headless host. Do not ask them to paste it into chat.
4. Recheck configuration, then return to the requested task.

**REST API or infrastructure as code (API key):** The REST API, Terraform provider, and Kubernetes Operator use an [API key](https://dashboard.ngrok.com/api-keys); the Operator also needs an agent authtoken. Confirm that the provider or Operator is installed, and have the user configure its API key there. The REST API needs no ngrok-specific tool; have the user configure `NGROK_API_KEY`. Do not ask for the key in chat. Confirm access with a read before making changes. See `ngrok-surfaces` for the chosen surface.

## 3. Offer adjacent capabilities when useful

For a broad request such as "set up ngrok for my coding agent", explain this optional sequence and skip what already works:

1. Install and authenticate the ngrok CLI if the agent needs to start local tunnels or endpoints.
2. [Install ngrok skills](https://ngrok.com/docs/for-agents/skills) if the user wants reusable guidance for exposing, securing, and troubleshooting services.
3. Connect the hosted MCP if the agent needs live account context or account-side actions.

If the user requested just one capability, complete that first. Then return to the user's original task.

## Notes for agents

- Agent authtokens start ngrok agent sessions; API keys administer account resources; hosted MCP uses OAuth or scoped PAT access. These credentials are not interchangeable.
- Never ask for or echo an authtoken, API key, PAT, or secret in chat. If one appears, do not repeat it; suggest rotation. MCP tools may list credential metadata, but they do not return secret values.
- Authentication setup is usually a one-time step for a machine or client. If a later ngrok command fails with an authentication error, check the chosen surface and credential before rotating anything.
- Run setup commands yourself when you have a shell, apart from steps that require the user to enter a secret or complete sign-in.
