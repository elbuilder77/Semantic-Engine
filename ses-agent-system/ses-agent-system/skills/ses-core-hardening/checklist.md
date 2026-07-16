# Checklist

- Identify all auth and middleware entry points.
- Confirm how API keys are parsed, validated, and rejected.
- Confirm how Redis dependency failures are handled.
- Check whether fail-open exists.
- Decide and document fail-closed behavior for production.
- Isolate any development-only bypass behind an explicit flag.
- Verify sensitive IDs, tokens, and internal details do not leak in responses.
- Verify secrets come from documented configuration, not scattered literals.
- Add or update tests for success and failure modes.
- Update docs when env/config behavior changes.
