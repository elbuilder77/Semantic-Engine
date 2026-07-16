# Checklist

- Locate the ingest entry points.
- Locate the watcher implementation.
- Reproduce duplicate or repeated ingest if present.
- Define the debounce strategy.
- Define how the same file/version is identified.
- Define safe reprocessing conditions.
- Check document counters and stats for placeholders.
- Add tests for duplicate event handling.
- Add tests for incremental ingest behavior if feasible.
- State what remains unproven at larger scale.
