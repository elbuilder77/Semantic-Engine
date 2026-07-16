# Commands

## Inspect product/docs surface
```powershell
Get-Content README.md -Raw
rg --files docs .github gateway portal ses-agent-system | Sort-Object
rg -n "compose|.env|install|troubleshoot|dashboard|CI|package|packaging|Production/Stable" README.md ROADMAP.md docs .github pyproject.toml
```

## Validate local security setup
```powershell
python scripts/rotate_local_secrets.py
git check-ignore -v .env ses-agent-system/keys.json
```

Do not claim Docker parity while no Compose file exists.

## Run baseline quality checks using the repo's native toolchain if present
```powershell
pytest -q
cargo test --manifest-path core_rs/Cargo.toml
if (Test-Path portal/node_modules) { npm --prefix portal run build }
```

## Mandatory release-readiness report
State:
- what works from a clean clone
- what still requires tribal knowledge
- what the packaging stance is
- what CI does today
- what is still missing for release confidence
