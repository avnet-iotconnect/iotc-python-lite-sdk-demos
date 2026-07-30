# i.MX95 Onboarding Portal

Self-service signup for the [GenAI Flow demo](../README.md): a visitor enters name/email/company on a
webpage and gets their **own /IOTCONNECT entity**, an invited user account, an `iMX95genai` device, and a
downloadable **board kit** (cert + key + `iotcDeviceConfig.json`). Copying the kit's three files onto a
FRDM i.MX95 running the demo connects it to *their* private dashboard.

Runs against the **AWS UAT** environment (`poc`). Live at the API Gateway URL for the `imx95-portal` API
(account 761303338807, us-east-1).

## Flow

```
visitor ──> signup page ──> Lambda ──> DynamoDB (pending)
                              │
              ┌───────────────┴─ event code matches? ──> instant onboard
              ▼
   SES email to approver: [Approve] [Reject]  (one click, signed links)
              ▼
   onboard: Entity under IMX95-Portal ─> user invited (IOTCONNECT sends the email)
            ─> iMX95genai device + self-signed cert ─> kit ready
              ▼
   applicant's page auto-updates ──> downloads board kit (.zip)
```

- **Approval is one click from the approver's inbox** — no console needed. An optional **event code**
  (Lambda env var `EVENT_CODE`) onboards instantly for booths; clear the variable to disable.
- Applicant emails come from IOTCONNECT itself (the entity-create welcome invite) — SES is only used for
  the approval notification, so the SES sandbox is fine (verify the approver address once).

## Components

| File | What it is |
|---|---|
| `iotc_client.py` | IOTCONNECT REST client (discovery → basic-token → login → entity/user/device). Shared by the Lambda and local tooling. |
| `lambda_function.py` | The whole backend: serves the signup page at `/`, plus `/api/signup`, `/api/status/{id}`, `/api/approve/{id}`, `/api/reject/{id}`, `/api/kit/{id}`. |
| `site/index.html` | Signup page (served by the Lambda — same origin, no S3/CloudFront needed). |
| `probe.py` | Local smoke test: login + entity/role/template lookups. |
| `aws-deploy-policy.json` | IAM policy for the deploying user. |

## AWS resources (us-east-1, account 761303338807)

- Lambda `imx95-portal-api` (python3.12, 512 MB, 90 s) with `cryptography` vendored for device-cert
  generation; env vars: `APPROVER_EMAIL`, `EVENT_CODE`, and optional overrides `PORTAL_PARENT`,
  `TEMPLATE_GUID`, `ADMIN_ROLE`, `SECRET_ID`, `TABLE`.
- HTTP API `imx95-portal` → Lambda (quick-create, `$default` route).
- DynamoDB `imx95-portal-requests` (id, token, admin_token, state, onboard JSON).
- Secrets Manager `imx95-portal/iotconnect`: `{solution_key, admin_user, admin_pass, env, pf}` — the
  **only** place credentials live.
- SES verified identity for the approver email.
- IAM role `imx95-portal-lambda` (logs + the table + the secret + `ses:SendEmail`).

## Deploying updates

Package = `lambda_function.py` + `iotc_client.py` + `index.html` + vendored `cryptography` manylinux wheels
(`pip download cryptography --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12`),
zipped flat, then `aws lambda update-function-code --function-name imx95-portal-api --zip-file fileb://lambda.zip`.

## Guardrails

- All portal writes are scoped under the `IMX95-Portal` entity — never touches the rest of the shared UAT tree.
- Kit/status URLs carry per-request random tokens; approve/reject links carry a separate admin token.
- Entity names are sanitized + de-duplicated; device UIDs are random (`p95` + 9 hex).
