# Commands

## Locate endpoints and tests
```powershell
rg -n "@app\.(get|post|delete)|/api/v1" gateway/server.py gateway/test_gateway.py
```

## Run targeted tests first
```powershell
pytest -q gateway/test_gateway.py
```

## Run integration subset if present
```powershell
if (Test-Path tests/integration) { pytest -q tests/integration }
```

## Validate app startup locally
```powershell
pytest -q
```

## Real-service validation

The repository currently has no Compose definition. Treat service-backed API
coverage as unverified until one is added and validated.

## If the repo uses another command runner, prefer the native one
Use `pytest` directly unless the repository later adds a canonical runner.

## Mandatory report
For each endpoint, state:
- status before
- status after
- tests added/updated
- Docker validation result
