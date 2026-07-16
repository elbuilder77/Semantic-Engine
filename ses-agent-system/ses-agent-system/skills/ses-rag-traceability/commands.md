# Commands

## Locate RAG and evidence flow
```powershell
rg -n "citation|source|rag|retrieve|export|pdf|answer|evidence|trace|source_path" ses gateway tests
```

## Run targeted tests
```powershell
pytest -q tests -k "rag or citation or source or export or answer"
```

## If integration coverage exists, run it
```powershell
if (Test-Path tests/integration) { pytest -q tests/integration -k "answer or export" }
```

## Inspect output schema candidates
```powershell
rg -n "BaseModel|TypedDict|schema|response_model|pydantic" gateway ses
```

## When adding fixtures, keep them deterministic
- use fixed documents
- use fixed queries
- assert source presence, not vague “good answer” narratives

## Mandatory report
State:
- where source traceability starts
- where it is lost, if anywhere
- what was fixed
- how empty-answer behavior now works
