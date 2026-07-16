# SES Agent System

This directory is now part of the SES repository and contains execution rules,
not a standalone multi-agent runtime.

## Integrated structure

- `../AGENTS.md`: canonical repository-wide entrypoint.
- `ses-agent-system/AGENTS.md`: detailed SES execution and phase-gate policy.
- `ses-agent-system/skills/`: eight SES-specific execution SOPs.
- `ai-agent-kernel/`: generic source rules from commit `741e904`, flattened into
  this repository because its former remote is not currently accessible.
- `keys.example.json`: non-secret schema example.

Local state is deliberately excluded from Git:

- `keys.json`: rotated Ed25519 signing keypair.
- `*.db`: local agent decision/state databases.
- repository-root `.env`: local Gateway administrator key and configuration.

Rotate local secrets with:

```powershell
python scripts/rotate_local_secrets.py
```

The command never prints secret values. Production deployments should use their
secret manager and set `GATEWAY_ADMIN_KEY` explicitly.
