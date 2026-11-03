# ngrok Agent Skills

A collection of skills for AI coding agents, covering how to expose local services, route and secure traffic, receive webhooks, and more.

Skills follow the [Agent Skills](https://agentskills.io/) format, so this repo works as a standalone skill pack and as a plugin for Claude Code, Cursor, ChatGPT, and Codex.

## Connect your agent to ngrok's MCP server

Follow the [ngrok MCP quickstart](https://ngrok.com/docs/mcp-server) to connect an AI client and inspect or manage your account. Once connected, the skills can check live endpoints, agents, and traffic instead of asking you. The Claude Code, Cursor, and Codex plugin packages include MCP connection configuration; a standalone skills install does not. Sign in through the client after installation. The ngrok CLI or an SDK starts tunnels from your machine.

## Installation

Any [Agent Skills](https://agentskills.io/)-compatible agent:

```bash
npx skills add ngrok/skills
```

Or install as a plugin:

- **Claude Code** (adds `/ngrok:*` slash commands):

  ```
  /plugin marketplace add ngrok/skills
  /plugin install ngrok@ngrok
  ```

- **Cursor:** Customize → Plugins → Add marketplace → From GitHub Repository → `ngrok/skills`.
- **ChatGPT and Codex:** run the command below, then restart and install **ngrok** from the Plugins Directory.

  ```bash
  codex plugin marketplace add ngrok/skills
  ```

## Skills

| Skill                      | Covers                                                                                                                                | Use when                                                                                             |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `expose-localhost`         | Give a local service a public URL — HTTP, or raw TCP for SSH, RDP, and databases                                                      | "Expose my local server", "Make my app publicly accessible", "SSH into a box with no public IP"      |
| `secure-endpoint`          | Auth, rate limiting, IP rules, or a custom response in front of an endpoint, without touching application code                        | "Require Google login on my ngrok URL", "Only allow my office IP range", "Put up a maintenance page" |
| `receive-webhooks`         | Receive webhooks from Stripe, GitHub, and 70+ other providers, with signature verification at the edge                                | "Test Stripe webhooks locally", "One endpoint for webhooks from several providers"                   |
| `run-mcp-gateway`          | Expose an MCP server under development so Claude, OpenAI, or another provider can connect to it, each with its own credential         | "Let Claude connect to my local MCP server"                                                          |
| `provision-sandbox-access` | Give every sandbox, container, customer device, or tenant its own isolated endpoint, provisioned programmatically from a controlplane | "Each sandbox needs its own SSH access", "One endpoint per customer"                                 |
| `troubleshoot-ngrok`       | Diagnose ngrok errors                                                                                                                 | "What does ERR_NGROK_3200 mean?", "Works on localhost, 400 through the ngrok URL"                    |
| `ngrok-setup`              | Set up and authenticate ngrok on the right surface: ngrok CLI, SDK, API, infrastructure as code, or hosted MCP                        | "Set up ngrok", "Set up ngrok MCP", "ngrok auth error"                                               |

### Supporting References

Two skills are reference material rather than tasks. The skills above load them automatically — you do not invoke them directly, but they're installed as part of the set.

| Skill            | Covers                                                                                                                                                          |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ngrok-engine`   | Endpoint types (agent, cloud, internal), HTTP vs TCP, and Traffic Policy — the rule language, plus a reference for all 26 traffic policy actions                |
| `ngrok-surfaces` | How to apply configuration on each surface: agent CLI and `ngrok.yml`, the Go/JavaScript/Python/Rust SDKs, the REST API, Terraform, and the Kubernetes Operator |

## Usage

Skills are automatically available once installed. The agent uses them when a relevant task is detected.

**Examples:**

```
Expose my app on port 3000 to the internet
```

```
Share my local server with Google OAuth so only people at @mycompany.com can access it
```

```
Receive Stripe webhooks and deliver them to a service that isn't publicly reachable
```

In Claude Code, you can also invoke a skill directly:

```
/ngrok:expose-localhost
```

Each skill contains:

- `SKILL.md` — instructions for the agent
- `references/` — supporting documentation (optional)

## License

MIT
