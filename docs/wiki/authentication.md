# Authentication

The CLI supports AttackIQ Account Token and JSON Web Token authentication.

## Configure Base URL

```bash
attackiq config set --base-url https://example.attackiq.com
```

## Configure Account Token

```bash
attackiq auth set --account-token <token>
```

## Configure JWT

```bash
attackiq auth set --jwt <token>
```

## Check Configuration

```bash
attackiq config show
```

Secrets are masked in config output.

## Environment Overrides

Use environment variables for temporary credentials:

```bash
export ATTACKIQ_ACCOUNT_TOKEN=<token>
export ATTACKIQ_JWT=<jwt>
```

## Safety Notes

- Do not commit tokens, browser cookies, captured netlogs, or exported session data.
- Prefer environment variables for short-lived work.
- Keep TLS verification enabled unless explicitly testing a lab endpoint.
- Use dry-run mode before applying write operations.
