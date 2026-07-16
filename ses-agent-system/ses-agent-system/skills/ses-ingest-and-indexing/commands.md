# Commands

## Locate ingest code
```powershell
rg -n "watcher|ingest|index|reindex|debounce|Qdrant|document count|stats|placeholder" ses gateway tests
```

## Run targeted tests
```powershell
pytest -q tests -k "watcher or ingest or index or qdrant"
```

## If the repo has runnable ingest scripts, inspect them
```powershell
rg --files ses gateway tests | rg "ingest|watch|index|seed|load"
```

## Real-service validation

Record Qdrant-backed validation as pending until the repository contains its
canonical local service definition and integration fixtures.

## Mandatory report
State:
- duplicate-ingest cause
- debounce strategy chosen
- file identity strategy
- stats corrected or still pending
