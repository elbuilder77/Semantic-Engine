# Commands

Run these commands from the repository root.

## Repository scan
```powershell
Get-Location
git status --short --branch
rg --files -g '!**/.git/**' | Sort-Object
```

## Read execution sources
```powershell
Get-Content ROADMAP.md -Raw
Get-Content TASKS.md -Raw
Get-Content README.md -Raw
```

## Search phase-relevant code
```powershell
rg -n "api/v1|watcher|Qdrant|Redis|Ollama|benchmark|metrics|trace|GATEWAY_ADMIN_KEY" ses gateway tests portal core_rs
```

## Test/discovery scan
```powershell
rg --files tests gateway -g 'test_*.py' | Sort-Object
pytest --collect-only -q
Test-Path compose.yml
Test-Path docker-compose.yml
```

## Output template
After inspection, produce:
- active phase
- open phase gates
- chosen primary skill
- chosen secondary skill, if any
- one execution slice
- one validation plan
