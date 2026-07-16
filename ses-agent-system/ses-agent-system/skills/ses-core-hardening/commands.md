# Commands

## Locate hardening surface
```powershell
rg -n "middleware|rate limit|redis|api key|auth|hmac|secret|token|fail-open|fail-closed|GATEWAY_ADMIN_KEY" gateway ses tests .env.example
```

## Inspect env/config usage
```powershell
rg -n "os.getenv|load_dotenv|DEBUG|REDIS|API_KEY|SECRET|GATEWAY_CORS" gateway ses .env.example README.md docs
git check-ignore -v .env ses-agent-system/keys.json ses-agent-system/tempus.db
```

## Run targeted tests
```powershell
pytest -q gateway/test_gateway.py -k "auth or admin_key or rate_limit or cors or api_key"
```

## If no targeted tests exist, create them, then run:
```powershell
pytest -q
```

## Real-service validation

No Compose file exists yet. Record that as an open gate; do not invent a Docker
command until the repository contains a reviewed service definition.

## Mandatory report
State:
- current failure policy
- desired production policy
- tests added/updated
- any env vars introduced or changed
