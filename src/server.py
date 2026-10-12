"""IdentityIQ SCIM MCP server. Existing guarded write tools + documented read resources."""
import os
import re
from urllib.parse import quote

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()
mcp = FastMCP("SailPoint IdentityIQ MCP")
SCIM_URL = os.getenv("SCIM_BASE_URL", "").rstrip("/")
if not SCIM_URL and os.getenv("DEMO_MODE", "false").lower() != "true":
    raise RuntimeError("SCIM_BASE_URL must be configured")
if not SCIM_URL.startswith(("https://", "http://")):
    raise RuntimeError("SCIM_BASE_URL must be an HTTP(S) URL")
if SCIM_URL.startswith("http://") and os.getenv("ALLOW_INSECURE_SCIM", "false").lower() != "true":
    raise RuntimeError("Non-HTTPS SCIM requires explicit ALLOW_INSECURE_SCIM=true (local labs only)")
CORE = "urn:ietf:params:scim:schemas:core:2.0:User"
PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
SP_SCHEMA = "urn:ietf:params:scim:schemas:sailpoint:1.0:User"
WORKFLOW_SCHEMA = "urn:ietf:params:scim:schemas:sailpoint:1.0:LaunchedWorkflow"
TASK_RESULT_SCHEMA = "urn:ietf:params:scim:schemas:sailpoint:1.0:TaskResult"


def get_headers(write=False):
    token = os.getenv("SCIM_ACCESS_TOKEN", "").strip()
    if not token:
        token_url = os.getenv("SCIM_TOKEN_URL", "").strip()
        client_id = os.getenv("SCIM_CLIENT_ID", "").strip()
        secret = os.getenv("SCIM_CLIENT_SECRET", "").strip()
        if not all((token_url, client_id, secret)):
            raise ValueError("Missing SCIM OAuth configuration")
        response = requests.post(token_url, data={"grant_type": "client_credentials"},
                                 auth=(client_id, secret), timeout=15)
        response.raise_for_status()
        token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/scim+json"}
    if write:
        headers["Content-Type"] = "application/scim+json"
    return headers


def scim_request(method, path, params=None, payload=None):
    if os.getenv("DEMO_MODE", "false").lower() == "true":
        from demo_backend import demo_request
        return demo_request(method, path, params, payload)
    # No user-supplied arbitrary URLs: all paths are constructed by the trusted tool functions.
    try:
        response = requests.request(method, f"{SCIM_URL}/{path.lstrip('/')}",
                                    headers=get_headers(write=method != "GET"),
                                    params=params, json=payload, timeout=30)
        if not response.ok:
            return {"error": "SCIM request failed", "status_code": response.status_code,
                    "method": method, "details": response.text[:1000]}
        return response.json() if response.content else {}
    except (requests.RequestException, ValueError, KeyError) as exc:
        return {"error": "SCIM connection or configuration failed", "type": type(exc).__name__}


def scim_get(path, params=None):
    return scim_request("GET", path, params=params)


def safe_resource_id(resource_id):
    if not isinstance(resource_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", resource_id):
        raise ValueError("Invalid SCIM resource ID")
    return quote(resource_id, safe="")


def page_params(count, start_index):
    return {"count": max(1, min(int(count), 100)), "startIndex": max(1, int(start_index))}


def list_resource(resource, count=20, start_index=1):
    return scim_get(resource, page_params(count, start_index))


def get_resource(resource, resource_id):
    return scim_get(f"{resource}/{safe_resource_id(resource_id)}")


def scim_filter_escape(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError("Search value must be 1-256 characters")
    return value.replace("\\", "\\\\").replace('"', '\\"')


def validate_write(approved):
    if os.getenv("DEMO_MODE", "false").lower() == "true":
        raise PermissionError("Writes are disabled in demo mode")
    if os.getenv("SAILPOINT_ENABLE_WRITES", "").lower() != "true":
        raise PermissionError("Writing is disabled. Set SAILPOINT_ENABLE_WRITES=true")
    if approved is not True:
        raise PermissionError("Explicit write approval required")


def allowed_user_ids():
    return {v.strip() for v in os.getenv("SAILPOINT_WRITE_USER_IDS", "").split(",") if v.strip()}


def check_target(user_id):
    safe_id = safe_resource_id(user_id)
    if user_id not in allowed_user_ids():
        raise PermissionError("Identity is not in SAILPOINT_WRITE_USER_IDS")
    identity = scim_get(f"Users/{safe_id}")
    if "error" in identity:
        raise ValueError("Unable to verify identity")
    if identity.get("id") != user_id:
        raise ValueError("Identity ID verification failed")
    if identity.get(SP_SCHEMA, {}).get("capabilities", []):
        raise PermissionError("Identity has privileged capabilities; write blocked")
    if identity.get("userName", "").lower() == "spadmin":
        raise PermissionError("Administrator identity is protected")
    return identity


def ensure_patch_supported():
    config = scim_get("ServiceProviderConfig")
    if "error" in config or config.get("patch", {}).get("supported") is not True:
        raise RuntimeError("Cannot verify SCIM PATCH support. No changes submitted")


def allowed_workflows():
    return {v.strip() for v in os.getenv("SAILPOINT_ALLOWED_WORKFLOWS", "").split(",") if v.strip()}


# Original 15 MCP tools (same public tool names and compatible inputs).
@mcp.tool()
def test_connection() -> dict:
    """Verify IdentityIQ connectivity using ServiceProviderConfig."""
    config = scim_get("ServiceProviderConfig")
    return {"status": "connected" if "error" not in config else "unavailable", "provider": config if "error" in config else {"verified": True},
            "writes_enabled": os.getenv("SAILPOINT_ENABLE_WRITES", "").lower() == "true"}


@mcp.tool()
def get_users(count: int = 20, start_index: int = 1) -> dict:
    """List IdentityIQ Users with pagination."""
    return list_resource("Users", count, start_index)


@mcp.tool()
def get_user(username: str) -> dict:
    """Find an IdentityIQ User by exact username."""
    return scim_get("Users", {"filter": f'userName eq "{scim_filter_escape(username)}"', "count": 10})


@mcp.tool()
def get_user_by_id(user_id: str) -> dict:
    """Retrieve a User by SCIM ID."""
    return get_resource("Users", user_id)


@mcp.tool()
def get_groups(count: int = 20) -> dict:
    """List Groups if supported by the deployed SCIM service."""
    return list_resource("Groups", count)


@mcp.tool()
def get_scim_resources() -> dict:
    """Discover SCIM ResourceTypes supported in this installation."""
    return scim_get("ResourceTypes")


@mcp.tool()
def get_scim_config() -> dict:
    """Inspect SCIM ServiceProviderConfig."""
    return scim_get("ServiceProviderConfig")


@mcp.tool()
def create_user(username: str, first_name: str, last_name: str, approved: bool = False) -> dict:
    """Create a User after explicit approval and server-side writes enablement."""
    validate_write(approved)
    username, first_name, last_name = username.strip(), first_name.strip(), last_name.strip()
    if not all((username, first_name, last_name)) or username.lower() == "spadmin" or not re.fullmatch(r"[A-Za-z0-9_.@-]{1,128}", username):
        raise ValueError("Invalid or protected username/name")
    return scim_request("POST", "Users", payload={"schemas": [CORE], "userName": username,
                        "name": {"givenName": first_name, "familyName": last_name},
                        "displayName": f"{first_name} {last_name}", "active": True})


@mcp.tool()
def update_user_display_name(user_id: str, display_name: str, approved: bool = False) -> dict:
    """PATCH a protected allowlisted User's displayName after approval."""
    validate_write(approved)
    check_target(user_id)
    ensure_patch_supported()
    if not display_name.strip():
        raise ValueError("Display name cannot be empty")
    return scim_request("PATCH", f"Users/{safe_resource_id(user_id)}", payload={
        "schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "displayName", "value": display_name.strip()}]})


@mcp.tool()
def list_workflows(count: int = 20, start_index: int = 1) -> dict:
    """List existing IdentityIQ workflows, including business processes and lifecycle events."""
    return list_resource("Workflows", count, start_index)


@mcp.tool()
def get_workflow(workflow_id: str) -> dict:
    """Get workflow metadata by SCIM ID. Read-only; does not retrieve complete workflow XML."""
    return get_resource("Workflows", workflow_id)


@mcp.tool()
def list_launched_workflows(count: int = 20, start_index: int = 1) -> dict:
    """List IdentityIQ workflow launch executions and exposed metadata."""
    return list_resource("LaunchedWorkflows", count, start_index)


@mcp.tool()
def get_launched_workflow(execution_id: str) -> dict:
    """Get a launched workflow execution by SCIM ID."""
    return get_resource("LaunchedWorkflows", execution_id)


@mcp.tool()
def launch_workflow(workflow_name: str, approved: bool = False) -> dict:
    """Launch an existing allowlisted no-input workflow only after explicit approval."""
    validate_write(approved)
    workflow_name = workflow_name.strip()
    if not workflow_name or workflow_name not in allowed_workflows():
        raise PermissionError("Workflow is not in SAILPOINT_ALLOWED_WORKFLOWS")
    result = scim_get("Workflows", {"filter": f'name eq "{scim_filter_escape(workflow_name)}"', "count": 10})
    if "error" in result:
        return result
    schema = "urn:ietf:params:scim:schemas:sailpoint:1.0:Workflow"
    matches = [w for w in result.get("Resources", []) if
               w.get("name") == workflow_name or w.get(schema, {}).get("name") == workflow_name]
    if len(matches) != 1:
        return {"error": "Workflow lookup did not return exactly one match", "matches": len(matches)}
    # This tool is strictly for operator-confirmed NO-INPUT workflows; cannot infer parameters.
    return scim_request("POST", "LaunchedWorkflows", payload={
        "schemas": [WORKFLOW_SCHEMA, TASK_RESULT_SCHEMA],
        WORKFLOW_SCHEMA: {"workflowName": workflow_name, "input": []}})


@mcp.tool()
def set_user_active(user_id: str, active: bool, approved: bool = False) -> dict:
    """Enable or disable an allowlisted nonprivileged User with explicit approval."""
    validate_write(approved)
    check_target(user_id)
    ensure_patch_supported()
    return scim_request("PATCH", f"Users/{safe_resource_id(user_id)}", payload={
        "schemas": [PATCH_SCHEMA], "Operations": [{"op": "replace", "path": "active", "value": active}]})


# New tools: named, documented IdentityIQ SCIM GET endpoints only.
@mcp.tool()
def list_accounts(count: int = 20, start_index: int = 1) -> dict:
    """List IdentityIQ Account resources; read-only."""
    return list_resource("Accounts", count, start_index)


@mcp.tool()
def get_account(account_id: str) -> dict:
    """Get IdentityIQ Account by SCIM ID; read-only."""
    return get_resource("Accounts", account_id)


@mcp.tool()
def list_alerts(count: int = 20, start_index: int = 1) -> dict:
    """List IdentityIQ Alerts; read-only."""
    return list_resource("Alerts", count, start_index)


@mcp.tool()
def get_alert(alert_id: str) -> dict:
    """Get an IdentityIQ Alert by SCIM ID; read-only."""
    return get_resource("Alerts", alert_id)


@mcp.tool()
def list_applications(count: int = 20, start_index: int = 1) -> dict:
    """List configured IdentityIQ Applications; read-only."""
    return list_resource("Applications", count, start_index)


@mcp.tool()
def get_application(application_id_or_name: str) -> dict:
    """Get an IdentityIQ Application by exact ID or name where supported; read-only."""
    if not isinstance(application_id_or_name, str) or not re.fullmatch(r"[A-Za-z0-9_ .:-]{1,256}", application_id_or_name):
        raise ValueError("Invalid application ID or name")
    return scim_get(f"Applications/{quote(application_id_or_name, safe='')}")


@mcp.tool()
def list_entitlements(count: int = 20, start_index: int = 1) -> dict:
    """List IdentityIQ Entitlements; read-only."""
    return list_resource("Entitlements", count, start_index)


@mcp.tool()
def get_entitlement(entitlement_id: str) -> dict:
    """Get an IdentityIQ Entitlement by SCIM ID; read-only."""
    return get_resource("Entitlements", entitlement_id)


@mcp.tool()
def list_roles(count: int = 20, start_index: int = 1) -> dict:
    """List IdentityIQ Roles; read-only."""
    return list_resource("Roles", count, start_index)


@mcp.tool()
def get_role(role_id: str) -> dict:
    """Get an IdentityIQ Role by SCIM ID; read-only."""
    return get_resource("Roles", role_id)


@mcp.tool()
def list_task_results(count: int = 20, start_index: int = 1) -> dict:
    """List IdentityIQ TaskResults (scheduled/background job outcomes); read-only."""
    return list_resource("TaskResults", count, start_index)


@mcp.tool()
def get_task_result(task_result_id: str) -> dict:
    """Get IdentityIQ TaskResult by SCIM ID; read-only."""
    return get_resource("TaskResults", task_result_id)


@mcp.tool()
def list_policy_violations(count: int = 20, start_index: int = 1) -> dict:
    """List IdentityIQ PolicyViolations; read-only."""
    return list_resource("PolicyViolations", count, start_index)


@mcp.tool()
def get_policy_violation(violation_id: str) -> dict:
    """Get IdentityIQ PolicyViolation by SCIM ID; read-only."""
    return get_resource("PolicyViolations", violation_id)


@mcp.tool()
def list_object_config(count: int = 20, start_index: int = 1) -> dict:
    """List IdentityIQ ObjectConfig resources; read-only."""
    return list_resource("ObjectConfig", count, start_index)


@mcp.tool()
def get_object_config(config_id: str) -> dict:
    """Get an IdentityIQ ObjectConfig by SCIM ID; read-only."""
    return get_resource("ObjectConfig", config_id)


@mcp.tool()
def list_scim_schemas(count: int = 20, start_index: int = 1) -> dict:
    """List IdentityIQ SCIM Schemas; read-only discovery."""
    return list_resource("Schemas", count, start_index)


@mcp.tool()
def get_scim_schema(schema_id: str) -> dict:
    """Retrieve a SCIM Schema by ID when supported; read-only."""
    return get_resource("Schemas", schema_id)


@mcp.tool()
def get_scim_resource_type(resource_type_id: str) -> dict:
    """Retrieve an individual SCIM ResourceType by ID; read-only."""
    return get_resource("ResourceTypes", resource_type_id)


@mcp.tool()
def search_workflows_by_name(workflow_name: str) -> dict:
    """Find workflow metadata by exact workflow name, without launching anything."""
    return scim_get("Workflows", {"filter": f'name eq "{scim_filter_escape(workflow_name)}"', "count": 20})


@mcp.tool()
def probe_scim_resources() -> dict:
    """Check which documented read-only IIQ resources are reachable (up to 10 GET requests)."""
    resources = ["Accounts", "Alerts", "Applications", "Entitlements", "ObjectConfig",
                 "PolicyViolations", "Roles", "Schemas", "TaskResults", "Workflows"]
    checked = {}
    for resource in resources:
        result = scim_get(resource, {"count": 1, "startIndex": 1})
        checked[resource] = {"accessible": "error" not in result,
                             "http_status": result.get("status_code") if isinstance(result, dict) else None}
    return {"checked": checked, "note": "Accessibility depends on version and caller permissions."}



# Supplementary SCIM read/search tools. Filter expressions are administrator-provided;
# they are GET-only and passed as query parameters, never URLs.

def _search(resource: str, field: str, value: str, count: int = 20) -> dict:
    return scim_get(resource, {"filter": f'{field} eq "{scim_filter_escape(value)}"', "count": max(1,min(count,100))})

def _query(resource: str, filter_expression: str = "", count: int = 20, start_index: int = 1, sort_by: str = "", sort_order: str = "") -> dict:
    p = page_params(count,start_index)
    if filter_expression:
        if len(filter_expression)>500 or any(x in filter_expression for x in ("\n","\r")):
            return {"error":"Invalid filter expression"}
        p["filter"] = filter_expression
    if sort_by: p["sortBy"] = sort_by
    if sort_order: p["sortOrder"] = sort_order
    return scim_get(resource,p)

@mcp.tool()
def find_accounts_by_username(username: str, count: int = 20) -> dict:
    """Read-only exact-match Accounts lookup, subject to SCIM filter support."""
    return _search("Accounts", "userName", username, count)

@mcp.tool()
def find_applications_by_name(name: str, count: int = 20) -> dict:
    """Read-only exact-match Applications lookup, subject to SCIM filter support."""
    return _search("Applications", "name", name, count)

@mcp.tool()
def find_roles_by_name(name: str, count: int = 20) -> dict:
    """Read-only exact-match Roles lookup, subject to SCIM filter support."""
    return _search("Roles", "name", name, count)

@mcp.tool()
def find_entitlements_by_display_name(display_name: str, count: int = 20) -> dict:
    """Read-only exact-match Entitlements lookup, subject to SCIM filter support."""
    return _search("Entitlements", "displayName", display_name, count)

@mcp.tool()
def find_alerts_by_name(name: str, count: int = 20) -> dict:
    """Read-only exact-match Alerts lookup, subject to SCIM filter support."""
    return _search("Alerts", "name", name, count)

@mcp.tool()
def find_task_results_by_name(name: str, count: int = 20) -> dict:
    """Read-only exact-match TaskResults lookup, subject to SCIM filter support."""
    return _search("TaskResults", "name", name, count)

@mcp.tool()
def find_policy_violations_by_identity(identity_id: str, count: int = 20) -> dict:
    """Read-only exact-match PolicyViolations lookup, subject to SCIM filter support."""
    return _search("PolicyViolations", "identityId", identity_id, count)

@mcp.tool()
def find_users_by_display_name(display_name: str, count: int = 20) -> dict:
    """Read-only exact-match Users lookup, subject to SCIM filter support."""
    return _search("Users", "displayName", display_name, count)

@mcp.tool()
def query_accounts(filter_expression: str = "", count: int = 20, start_index: int = 1) -> dict:
    """Read-only SCIM-filtered Accounts query."""
    return _query("Accounts",filter_expression,count,start_index)

@mcp.tool()
def query_roles(filter_expression: str = "", count: int = 20, start_index: int = 1) -> dict:
    """Read-only SCIM-filtered Roles query."""
    return _query("Roles",filter_expression,count,start_index)

@mcp.tool()
def query_entitlements(filter_expression: str = "", count: int = 20, start_index: int = 1) -> dict:
    """Read-only SCIM-filtered Entitlements query."""
    return _query("Entitlements",filter_expression,count,start_index)

@mcp.tool()
def query_task_results(filter_expression: str = "", count: int = 20, start_index: int = 1) -> dict:
    """Read-only SCIM-filtered TaskResults query."""
    return _query("TaskResults",filter_expression,count,start_index)

@mcp.tool()
def query_workflows(filter_expression: str = "", count: int = 20, start_index: int = 1) -> dict:
    """Read-only SCIM-filtered Workflows query."""
    return _query("Workflows",filter_expression,count,start_index)

@mcp.tool()
def query_launched_workflows(filter_expression: str = "", count: int = 20, start_index: int = 1) -> dict:
    """Read-only SCIM-filtered LaunchedWorkflows query."""
    return _query("LaunchedWorkflows",filter_expression,count,start_index)

@mcp.tool()
def get_workflow_by_name(workflow_name: str) -> dict:
    """Lookup workflow metadata by exact name."""
    return _search("Workflows","name",workflow_name)

@mcp.tool()
def check_policy_violations(simulation_request: dict, approved: bool = False) -> dict:
    """Submit approved non-provisioning policy simulation."""
    validate_write(approved)
    if not isinstance(simulation_request,dict) or not simulation_request.get("schemas"):
        return {"error":"Complete schema-compatible simulation payload required"}
    return scim_request("POST","CheckedPolicyViolations",payload=simulation_request)

@mcp.tool()
def scim_capability_matrix() -> dict:
    """Discover server-announced SCIM capabilities and resource types."""
    return {"service_provider_config":scim_get("ServiceProviderConfig"),"resource_types":scim_get("ResourceTypes")}

@mcp.tool()
def list_supported_public_operations() -> dict:
    """Describe supported SCIM operations, without implying plugin support."""
    return {"scim_write_tools":["create_user","update_user_display_name","set_user_active","launch_workflow","check_policy_violations"],"plugin_required":False,"demo_mode":os.getenv("DEMO_MODE", "false").lower() == "true","note":"Availability varies with IIQ version and authorization; no plugin operations are included."}



if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "http":
        # This server does not implement inbound OAuth. Deploy HTTP only behind
        # an authenticated reverse proxy or on private network infrastructure.
        if os.getenv("MCP_HTTP_PROXY_AUTHENTICATED", "false").lower() != "true":
            raise RuntimeError("HTTP mode requires MCP_HTTP_PROXY_AUTHENTICATED=true and an authenticated upstream")
        mcp.run(transport="streamable-http", host=os.getenv("MCP_HOST", "0.0.0.0"),
                port=int(os.getenv("MCP_PORT", "8000")))
    else:
        raise RuntimeError("MCP_TRANSPORT must be stdio or http")
