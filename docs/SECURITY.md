# Security notes

Treat MCP tools as privileged API surfaces, not trusted prompts. Do not expose this service publicly with anonymous HTTP access. The application does not implement inbound OAuth, user-level authentication, session binding or production rate limits. An `approved` boolean is a code-level safeguard, not a verified human confirmation or a replacement for independent authorization.

For real IdentityIQ: TLS, least-privileged OAuth credentials, segregated test and production environments, restricted egress, protected secrets, request auditing, and protected ingress are mandatory considerations. Write support is off by default. Only add approved SCIM IDs to the change allowlist and approved workflows to the launch allowlist, after independently verifying workflow inputs and effects.

The demo backend provides fictional data and will refuse any write. Never commit `.env`, tokens, private key materials, or real identity data. Report security issues privately to the maintainer rather than posting credentials in public issues.
