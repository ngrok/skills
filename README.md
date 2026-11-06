# ngrok Agent Skills

A collection of skills for AI coding agents, covering how to expose local services, route and secure traffic, receive webhooks, and more.

Skills follow the [Agent Skills](https://agentskills.io/) format, so this repo works as a standalone skill pack and as a plugin for Claude Code, Cursor, ChatGPT, and Codex.

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
| `troubleshoot-ngrok`       | Diagnose any ngrok error from its docs page and your account's live state                                                             | "What does ERR_NGROK_3200 mean?", "Works on localhost, 400 through the ngrok URL"                    |
| `ngrok-setup`              | Get authenticated and pointed at the right surface — CLI, SDK, API, or infrastructure-as-code                                         | "Set up ngrok", "ngrok says I'm not authenticated"                                                   |

### Supporting References

Two skills are reference material rather than tasks. The skills above load them automatically — you do not invoke them directly, but they're installed as part of the set.

| Skill            | Covers                                                                                                                                                          |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ngrok-engine`   | Endpoint types (agent, cloud, internal), HTTP vs TCP, and Traffic Policy — the rule language, plus a reference for all 26 traffic policy actions                |
| `ngrok-surfaces` | How to apply configuration on each surface: agent CLI and `ngrok.yml`, the Go/JavaScript/Python/Rust SDKs, the REST API, Terraform, and the Kubernetes Operator |

## ngrok MCP server

When the ngrok MCP server is connected, the skills use it to check your account's live state, such as endpoints, agents, and traffic, instead of asking you. The plugin installs include the server. To sign in or set it up another way, see the [ngrok MCP server docs](https://ngrok.com/docs/mcp-server).

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

## Releases

Every merge to `main` that changes `skills/` (or the bundle script) publishes a dated release, after the same checks as a pull request (`.github/workflows/release.yml`). A maintainer can also run the workflow by hand from `main`. The newest release is always at `https://github.com/ngrok/skills/releases/latest`.

### Version format

- **Tag.** The tag is `v` followed by the version, for example `v2026.11.04`.
- **Version.** The version is the UTC date of the release run, written as `YYYY.MM.DD` with a zero-padded month and day.
  - The first release of a UTC day has no suffix.
  - Each later release that day appends `.N`, starting at `.1`: `2026.11.04`, then `2026.11.04.1`, then `2026.11.04.2`.
- **Ordering.** Compare versions segment by segment as integers, and treat a missing segment as 0. So `2026.11.04` < `2026.11.04.1` < `2026.11.04.10` < `2026.11.05`. Do not compare them as strings: `.10` sorts before `.9` as text.
- **Not semver.** The zero padding makes the version invalid semver. That is acceptable, because nothing reads these tags as semver. Do not copy the version into the plugin manifests' version fields. If a plugin format later needs a version, that is separate work.
- **Strictly increasing.** Every new tag must be greater than every existing `v*` tag. A same-day suffix and a UTC clock keep it that way. The workflow also checks it (`scripts/next_version.py` exits non-zero otherwise).

The reference implementation of the ordering rule is `version_key()` in [`scripts/next_version.py`](scripts/next_version.py). Anything that compares skills versions should implement the same rule.

### Assets

Each release carries two files:

| Asset | Contents |
| --- | --- |
| `skills.tar.gz` | One top-level directory per skill, with that skill's files, and nothing else. There is no wrapping `skills/` directory. Built with `git archive` of the committed `skills/` tree by [`scripts/build_bundle.sh`](scripts/build_bundle.sh). |
| `skills.tar.gz.sha256` | One line in `sha256sum` format: `<hex>  skills.tar.gz`. |

Releases are immutable: once published, a release's assets and tag cannot change.

To fetch the newest release without the GitHub API, read the `Location` header of `https://github.com/ngrok/skills/releases/latest` without following it. It ends in `/releases/tag/v<version>`. Then download `https://github.com/ngrok/skills/releases/download/v<version>/skills.tar.gz` and `skills.tar.gz.sha256`.

## License

MIT
