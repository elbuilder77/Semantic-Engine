# Purpose

Use this skill to make multi-provider LLM behavior controlled instead of accidental.

This skill owns:
- current Ollama behavior and any future provider added to live code
- timeout and retry behavior
- provider degradation rules
- provider-specific error surfacing
- deterministic selection logic when multiple providers are available

## Core responsibility

Make provider behavior explicit, testable, and observable.
