# Purpose

Use this skill to decide **what should be executed now** and **what must wait**.

This skill is the orchestration layer for SES delivery. It translates `ROADMAP.md`, `TASKS.md`, and the live repository state into one narrow, validated execution slice.

This skill does not exist to produce strategy theater. It exists to:
- identify the active phase
- choose the right skill for the current slice
- define scope small enough to complete in one iteration
- enforce phase gates
- prevent random work

## Core responsibility

Convert roadmap intent into executable work with a clear done condition.
