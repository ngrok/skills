# `verify-webhook`

**Generated from ngrok's published documentation - do not hand-edit.**

Validate incoming signatures against a known secret to ensure authenticity.

- **Phases:** `on_http_request`
- **Ends chain:** no
- **Categories:** security

## Configuration

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `provider` | string | yes | The name of the provider to verify webhook requests from. Value must be a supported provider identifier. Don't see your provider? Request support for it here. |
| `secret` | string | yes | The secret key used to validate webhook requests from the specified provider. Supports CEL Interpolation. Accepts CEL interpolation. |
| `enforce` | bool | no | When `true`, ngrok halts the request if the webhook isn't valid, and no further actions run. However, when `false`, subsequent actions run even if the webhook isn't valid. Default `true`. |

## Result variables

Readable from `expressions` in later rules once this action has run.

- `actions.ngrok.verify_webhook.verified` (bool)
- `actions.ngrok.verify_webhook.error.code` (string)
- `actions.ngrok.verify_webhook.error.message` (string)

## Example

```yaml
on_http_request:
  - actions:
      - type: verify-webhook
        config:
          provider: gitlab
          secret: secret!
      - type: custom-response
        config:
          status_code: 200
          headers:
            content-type: text/plain
          body: GitLab webhook verified
```

Docs: <https://ngrok.com/docs/gateway/traffic-policy/actions/verify-webhook>
