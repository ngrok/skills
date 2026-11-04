---
name: troubleshoot-ngrok
description: Diagnose and fix ngrok errors and connection problems. Looks up the ERR_NGROK code (or the error message) in ngrok's error docs, then checks the account's live state - endpoints, agents, traffic, limits - to find the specific cause. Covers offline endpoints (ERR_NGROK_3200), upstream connection failures (ERR_NGROK_8012), agent authentication and session limits, Traffic Policy errors, and TLS errors. Use when an ngrok URL returns an error, an agent won't start or stay connected, or the user pastes an ngrok error code or message. Use when the user says "ngrok says endpoint offline", "ERR_NGROK_3200", "my tunnel isn't working", "why is my ngrok URL down", or "what does this ngrok error mean".
license: MIT
metadata:
  author: ngrok
  version: "1.1"
  category: troubleshooting
  surface: job
compatibility: Works best with the ngrok MCP server connected, for error lookup and live account state. Without it, needs web access to ngrok.com/docs and the ngrok CLI.
---

# Troubleshoot ngrok

Diagnose a failing ngrok endpoint or agent in three steps: get the error, read its docs page, then check live state to find which cause applies.

## 1. Get the error

ngrok errors carry an `ERR_NGROK_<code>` code. It shows on the error page in the browser, in agent output, in API responses, and in the traffic inspector. Some codes are numbers (`ERR_NGROK_8012`) and some are names (`ERR_NGROK_AGENT_NOT_FOUND`).

Get the code. If the user has only the message, keep the exact text, with its values. If there is no error at all, go to [By symptom](#by-symptom-no-error).

## 2. Read the error's docs page

Every code has a page with its causes and fixes. Do not explain a code from memory: codes are specific, and a near guess sends the user down the wrong path.

- **ngrok MCP server with `docs_get_error`:** call it with `code`, or with `message` when there is no code. If it returns several codes for one message, ask the user for the code. Do not pick one.
- **Otherwise:** if you only have a message, obtain the code from the error page or agent output, or ask the user for it; do not guess a code from the message. Once you have the code, fetch `https://ngrok.com/docs/errors/err_ngrok_<code>.md`, with the code in lowercase and without the `ERR_NGROK_` prefix. For example, `ERR_NGROK_8012` is `err_ngrok_8012.md`. A 404 means the code is wrong; check it with the user.

`docs_search` does not find error pages. Do not use it for an error code.

## 3. Find which cause applies

An error page lists the possible causes. Check the account to find the one that applies, instead of asking the user to check each one.

With the ngrok MCP server:

| Question | Tool |
| --- | --- |
| Is anything serving this URL? | `get_resource` with the URL. `gw_list_endpoints` shows what the account serves; a near-miss URL is a common cause. |
| Is the agent connected, and is its version current? | `gw_list_agents`: connected agents, versions, and any deprecation deadline. |
| What happened to this one request? | `gw_get_traffic_inspector_request` with the request ID from the ngrok error page. |
| Which requests failed? | `gw_query_traffic_inspector`: each row carries its ngrok error code. Filter by host, status, or path. |
| TCP or TLS endpoint failures | `gw_query_connections` (it filters by error code), then `gw_get_connection`. |
| Is the account at a limit? | `platform_get_enforced_limits`. `platform_get_usage` reports consumption, not caps. |
| Is the Traffic Policy valid? | `gw_validate_traffic_policy` reports each problem with its line and column. |

Without the server, use the agent's own output (`ngrok http <port> --log stdout`), the local inspector at `http://localhost:4040`, and the [dashboard](https://dashboard.ngrok.com).

Then apply the fix from the page, and send the failing request again to confirm.

## Notes on the most common codes

The docs page has the full fix. These notes are what the page does not say.

- **ERR_NGROK_3200 (endpoint offline).** Nothing is serving the URL that was visited. Check two things: is an agent connected, and does it serve *exactly* this URL? A different subdomain or a typo gives the same error. When a *visitor* reports 3200, the owner's agent has usually stopped. There may be nothing for the visitor to fix.
- **ERR_NGROK_8012 (upstream connection failed).** ngrok works; the local service does not answer. Confirm the service runs on exactly the port and scheme the agent forwards to (`http` vs `https`, `localhost` vs `127.0.0.1` vs a container address).
- **Authentication errors** (for example ERR_NGROK_4018). Missing or invalid credential. Check which credential is in play first: the agent uses an authtoken, the API and IaC use an API key. Hand off to `ngrok-setup`.
- **Session limits** (for example ERR_NGROK_108). Another agent with the same account is already connected. `gw_list_agents` shows where it runs.

## By symptom (no error)

- **Works on localhost, 400 or rejected through the ngrok URL.** The app or dev server rejects the ngrok `Host` header. See `expose-localhost/references/TROUBLESHOOTING.md`. For internal endpoints, `--host-header=rewrite` (see `run-mcp-gateway`).
- **Agent exits at once on start.** A credential problem (see `ngrok-setup`) or a config file that does not parse. Run `ngrok config check`.
- **Traffic Policy has no effect.** The policy is not attached to the endpoint being hit, or an earlier rule ends the chain. Confirm the attachment on the user's surface (see `ngrok-surfaces`). See `ngrok-engine` for rule order.
- **TLS or certificate errors on an ngrok domain.** First check for an incident at [status.ngrok.com](https://status.ngrok.com). If there is none, something on the user's network is likely intercepting TLS: an ISP filter, a VPN, or endpoint security software on a managed machine. Ask the user to try another network, and to compare the certificate issuer with `openssl s_client -connect <host>:443 -servername <host>`.

## Notes for agents

- Run the checks yourself when you have the MCP server or a shell. Give the user the cause and the fix, not a list of things to check.
- Work from the code. If the code names the cause, do not guess around it.
- If the cause is a credential or a policy, hand off to `ngrok-setup` or `ngrok-engine`. Do not repeat their content here.
