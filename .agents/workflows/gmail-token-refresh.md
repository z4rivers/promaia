---
description: Refresh expired Gmail OAuth tokens for both accounts
---

# Gmail Token Refresh

When Gmail API calls fail with `invalid_grant: Token has been expired or revoked`, follow these steps.

## Quick Fix (90% of cases)

// turbo-all

1. Run the token refresh script:
```powershell
python tmp/force_refresh_gmail.py
```

2. A browser window will open for **zachary4rivers@gmail.com** — sign in and click "Allow"
3. A second browser window will open for **zackayak@gmail.com** — sign in and click "Allow"
4. Terminal should print `Success!` for both accounts

## What This Does

- Uses `InstalledAppFlow` from `google_auth_oauthlib` to get fresh OAuth tokens
- Saves tokens to **both** `credentials/zbrain/` AND `credentials/default/` (background workers read from `default/`)
- Does NOT touch the GCP client credentials file (`gmail_credentials.json`)

## File Locations

| File | Path | Purpose |
|------|------|---------|
| GCP Client Credentials | `credentials/zbrain/gmail_credentials.json` | App identity (NEVER overwrite) |
| Token (zachary4rivers) | `credentials/default/gmail_token.json` | User auth token |
| Token (zackayak) | `credentials/default/gmail_token_zackayak.json` | User auth token |
| Refresh Script | `tmp/force_refresh_gmail.py` | The script that does the refresh |

## ⚠️ DO NOT

- **DO NOT** run `maia workspace gmail-setup` — it asks to overwrite the GCP client credentials, which is wrong
- **DO NOT** run `python -m promaia.cli.main` — that module path doesn't exist. Use `python -m promaia` if you need the CLI
- **DO NOT** manually delete `gmail_credentials.json` — that's the app password from Google Cloud Console

## Verification

After refreshing, test with:
```powershell
python tmp/test_gmail_multimodal.py
```
Should print `Success!` and `Found message ... with attachment`.
