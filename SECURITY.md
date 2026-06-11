# Security Policy

## Reporting a vulnerability

Please do not open a public issue with API keys, OAuth tokens, private code, or exploit details.

If this repository has GitHub private vulnerability reporting enabled, use the **Security** tab to submit a private advisory. Otherwise, open a minimal public issue that says you found a security concern and ask for a private contact path.

## Scope

Virtuoso runs local commands and can send prompts/code to configured model providers. Treat API keys and project source code as sensitive.

The `/run` command uses lightweight local process isolation. It is intended for convenience, not as a hardened sandbox for untrusted code.
