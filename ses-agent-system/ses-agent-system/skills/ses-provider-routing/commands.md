# Commands

## Locate provider logic
```powershell
rg -n "Ollama|provider|fallback|retry|timeout|llm|EMBEDDING_PROVIDER" ses gateway tests .env.example
```

## Run provider-related tests
```powershell
pytest -q tests -k "provider or llm or fallback or ollama or openai or groq"
```

## Search config surface
```powershell
rg -n "OLLAMA|MODEL|TIMEOUT|RETRY|PROVIDER" .env.example ses gateway README.md docs
```

## If integration environment exists, validate fallback in practice
```powershell
if (Test-Path tests/integration) { pytest -q tests/integration -k "provider or fallback or answer" }
```

## Mandatory policy output
State explicitly:
- provider order
- timeout policy
- retry policy
- what triggers fallback
- what is surfaced to the caller
