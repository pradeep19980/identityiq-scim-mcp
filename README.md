# IdentityIQ SCIM MCP

A small, Python-only MCP server for exploring **SailPoint IdentityIQ SCIM v2** with an AI assistant. The focus is keeping the connector understandable: ordinary Python functions, explicit SCIM requests, and guarded changes.

This is an independent community project, not a SailPoint product. It does **not** need a Java plugin and does not claim to support undocumented IdentityIQ administration APIs.

**54 tools registered** · read-only demo mode · optional live SCIM connection · local-first

## Try it without IdentityIQ (demo mode)

The included fictional data lets you inspect identities, applications, roles, workflows and filters. You can explore the MCP interface without credentials or making network requests.

```bash
# Python 3.11+ recommended
python -m venv .venv
# macOS / Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set `DEMO_MODE=true` in your shell, then run `python src/server.py`. PowerShell:

```powershell
$env:DEMO_MODE="true"
python src/server.py
```

macOS / Linux:

```bash
DEMO_MODE=true python src/server.py
```

The server uses **stdio** by default. It waits for an MCP client (it is normal for the terminal to appear idle). To explore interactively, use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector), and point it at `python` with arguments `src/server.py` and the `DEMO_MODE=true` environment variable.

Try `test_connection`, `get_users`, `list_applications`, `list_workflows` and `find_users_by_display_name`. All demo data is synthetic. **Writes always fail in demo mode**, even with an approval flag.

## Connect to your own IdentityIQ installation

1. Verify that your IIQ instance provides the relevant SCIM v2 resource endpoints and that the API account is authorised.
2. Copy `.env.example` to `.env` and fill in **only your private local copy**.
3. Set `DEMO_MODE=false`, configure `SCIM_BASE_URL`, and provide OAuth credentials or an access token.
4. Run `python src/server.py`, then connect a local MCP host using stdio.

Example local host configuration (replace the path with your own absolute path):

```json
{
  "mcpServers": {
    "identityiq": {
      "command": "python",
      "args": ["/absolute/path/to/identityiq-scim-mcp/src/server.py"],
      "env": {"DEMO_MODE": "true"}
    }
  }
}
```

For real IIQ, replace `DEMO_MODE` with your connection-specific environment or use a local `.env` file. The exact host configuration varies by MCP client.

## What it can do

The full [54-tool catalogue](docs/TOOLS.md) includes users, groups, accounts, applications, roles, entitlements, workflows, policy-violation resources, tasks, schemas and capability discovery. **Five tools** can request changes or simulations in live mode, subject to the server's write controls and IIQ permissions.

`create_application`, `create_identity_attribute`, unrestricted provisioning and workflow-definition imports are **not included**. Public SCIM support for those actions has not been established. Some installations return 404 for ObjectConfig despite advertising its resource type.

## Safety defaults

- Live writes are **off** by default (`SAILPOINT_ENABLE_WRITES=false`). An `approved=true` argument is an additional guard, **not authenticated user consent**.
- Identity updates require an ID allowlist, and workflow launches require a name allowlist. Do not enable writes on a publicly accessible or anonymously callable MCP server.
- HTTP to IdentityIQ is blocked unless explicitly opted in for a trusted lab; use HTTPS in production.
- Never commit `.env`, access tokens, private keys, tenant hostnames, log exports or real identity records.
- Remote HTTP transport needs authenticated TLS termination, client-level permissions and careful network controls. This repository **does not implement inbound MCP OAuth** and is **not production-hardened** for public internet deployment.

See [security notes](docs/SECURITY.md).

## Developer workflow

```bash
pip install -r requirements-dev.txt
pytest -q
python -m compileall -q src
```

CI checks Python compilation, tool count and the read-only demo backend. Pull requests should include tests and avoid adding speculative endpoints to inflate the count.

## Docker (optional)

```bash
docker build -t identityiq-scim-mcp .
docker run --rm -i --env DEMO_MODE=true identityiq-scim-mcp
```

For local MCP hosts, direct Python stdio is simpler. AWS deployment is **not required** to publish or test this GitHub repository. If you deploy remotely, build the image into your own private environment behind properly authenticated TLS ingress; see [deployment notes](docs/DEPLOYMENT.md).

## Publish on GitHub

See [the step-by-step guide](docs/GITHUB.md), including both the website and CLI methods.

## Contributions

Issues and reproducible examples are welcome. For new tools, include the documented SCIM endpoint, supported IIQ versions, response examples with personal information removed, and read/write tests.

Released under the MIT License. SailPoint and IdentityIQ are trademarks of their respective owners.
