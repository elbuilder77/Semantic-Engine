# SES Repository Agent Rules

These rules apply to the entire repository. The live code and executable
validation are the source of truth; documentation describes intent and must be
corrected when it disagrees with runtime behavior.

## Session startup

Before implementation work:

1. Read `ROADMAP.md` and `TASKS.md` from the repository root.
2. Inspect the active branch, worktree changes, dependencies, and relevant code.
3. Read `ses-agent-system/ses-agent-system/AGENTS.md`.
4. Choose one primary SES skill and at most one secondary skill from
   `ses-agent-system/ses-agent-system/skills/`.
5. Define a narrow slice with an explicit validation command and done condition.

## Repository map

- `ses/`: Python RAG library and filesystem watcher.
- `gateway/`: FastAPI enterprise gateway and canonical static dashboard.
- `core_rs/`: optional PyO3 acceleration module.
- `portal/`: Next.js portal; do not claim it is operational unless it builds.
- `tests/`: Python tests; distinguish mocked tests from real service validation.
- `ses-agent-system/`: repository-specific execution rules and reusable SOPs.

## Security baseline

- Never commit `.env`, `ses-agent-system/keys.json`, databases, private keys, or
  raw API tokens.
- Production authentication and rate limiting fail closed.
- Development fallbacks require `DEBUG=true` and must be identified as local-only.
- API keys are displayed once, stored as hashes, and rotated through documented
  tooling or a production secret manager.
- Preserve unrelated user changes already present in the worktree.

## Evidence bar

Every implementation cycle must report:

- files changed;
- exact validation commands and results;
- what is now true;
- remaining risk;
- one next recommended slice.

Do not mark a phase complete based only on documentation, mocked tests, generated
artifacts, or the existence of CI configuration.
