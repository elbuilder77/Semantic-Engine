# SES Execution Tasks

This task list tracks gaps confirmed against the live repository. Update it only
when implementation and validation evidence exist.

## P0 - Security and repository rules

- [x] Integrate the SES agent rules at the repository root.
- [x] Ignore and rotate local Gateway and agent signing secrets.
- [x] Remove the known default Gateway administrator key.
- [x] Make production rate limiting fail closed.
- [x] Restrict Gateway CORS to configured origins.

## P1 - Correctness and integration

- [ ] Fix persistent Gateway usage telemetry and cover it with a non-permissive mock.
- [ ] Add real integration tests for SQLite, Qdrant, Redis, and Ollama failure paths.
- [ ] Add a reproducible local service stack before claiming Docker parity.
- [ ] Make changed-file reindexing atomic or recoverable.

## P2 - Productization

- [x] Complete the `portal/` client contract and validate lint/build/runtime routes.
- [ ] Align README and ROADMAP claims with validated runtime behavior.
- [x] Package the Rust extension as a CPython wheel and add Rust/Python integration tests.
- [ ] Run named ingestion and retrieval workloads before publishing scale claims.
