# Security Policy

The Intracept registry is a **data repo**: TOML rule files plus a generated
`registry.json` snapshot. There's no code that runs at request time. The
security-relevant concerns are:

1. A malicious PR slipping in a permissive verdict for a destructive command
   (e.g. flipping `rm -rf *` to `allow`).
2. A malicious PR adding a translation that hides what a flag actually does.
3. Secrets, internal hostnames, or other private data committed to the repo
   (e.g. via the coverage scraper).

## Reporting a vulnerability

Email [security@intracept.dev](mailto:security@intracept.dev). Do not file a
public GitHub issue.

Please include:

- The file/path involved and the proposed wrong-verdict or misleading
  translation.
- Where applicable, a reference to authoritative documentation (man page,
  vendor docs) showing the correct behavior.
- The registry commit hash where the issue is reproducible.

We will acknowledge within **3 business days** and aim to ship a fix within
**14 days** for verdict-flip / translation-accuracy issues, **30 days** for
broader hardening (CI scanners, schema constraints).

## Scope

In scope:

- TOML files under `tools/`.
- `registry.json` snapshot.
- The coverage report and any scripts that emit public artifacts from
  user-supplied data.
- Anything tracked in this repo on the public default branch.

Out of scope:

- Findings that require an attacker to commit code via a maintainer's
  GitHub account.

## Safe-harbor

We will not pursue legal action against researchers acting in good faith and
in compliance with this policy.
