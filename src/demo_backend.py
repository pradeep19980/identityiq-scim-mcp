"""Small deterministic, read-only SCIM emulator for trying tools without IdentityIQ.
No network access and no persistence; all data is synthetic.
"""
import re
from urllib.parse import unquote

USERS = [
    {"id":"demo-001", "userName":"alex.chen", "displayName":"Alex Chen", "active":True, "name":{"givenName":"Alex","familyName":"Chen"}, "schemas":["urn:ietf:params:scim:schemas:core:2.0:User"]},
    {"id":"demo-002", "userName":"sam.rivera", "displayName":"Sam Rivera", "active":True, "name":{"givenName":"Sam","familyName":"Rivera"}, "schemas":["urn:ietf:params:scim:schemas:core:2.0:User"]},
    {"id":"demo-003", "userName":"taylor.jones", "displayName":"Taylor Jones", "active":False, "name":{"givenName":"Taylor","familyName":"Jones"}, "schemas":["urn:ietf:params:scim:schemas:core:2.0:User"]},
]
DATA = {
 "Users": USERS,
 "Groups": [{"id":"grp-001","displayName":"Demo Engineering"}],
 "Applications": [{"id":"app-001","name":"Demo HR System","description":"Synthetic example"}],
 "Accounts": [{"id":"acct-001","userName":"alex.chen","displayName":"Alex Chen","application":"Demo HR System"}],
 "Roles": [{"id":"role-001","name":"Employee"}],
 "Entitlements": [{"id":"ent-001","displayName":"Viewer"}],
 "Workflows": [{"id":"wf-001","name":"Demo Joiner (read-only example)"}],
 "LaunchedWorkflows": [], "Alerts": [], "TaskResults": [], "PolicyViolations": [],
 "ObjectConfig": [],
 "Schemas": [{"id":"urn:ietf:params:scim:schemas:core:2.0:User","name":"User"}],
}
RESOURCE_TYPES = [{"id":name[:-1] if name.endswith("s") else name,"name":name[:-1] if name.endswith("s") else name,"endpoint":"/"+name} for name in DATA]
CONFIG={"schemas":["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],"patch":{"supported":False},"filter":{"supported":True},"sort":{"supported":False},"bulk":{"supported":False}}

def demo_request(method, path, params=None, payload=None):
    if method != "GET":
        return {"error":"Demo mode is read-only", "status_code":403}
    parts=[unquote(p) for p in path.strip("/").split("/")]
    kind=parts[0]
    if kind=="ServiceProviderConfig":return CONFIG
    if kind=="ResourceTypes":items=RESOURCE_TYPES
    elif kind in DATA:items=DATA[kind]
    else:return {"error":"Unknown demo resource","status_code":404}
    if len(parts)>1:
        matches=[row for row in items if row.get("id")==parts[1]]
        return matches[0] if matches else {"error":"Not found","status_code":404}
    rows=list(items)
    filt=(params or {}).get("filter", "")
    if filt:
        match=re.fullmatch(r'([A-Za-z][A-Za-z0-9]*)\s+eq\s+"((?:\\.|[^"])*)"',filt)
        if not match:return {"error":"Demo supports simple exact-match eq filters only","status_code":400}
        field,value=match.groups()
        value=value.replace('\\"','"').replace('\\\\','\\')
        rows=[row for row in rows if str(row.get(field,""))==value]
    total=len(rows)
    start=max(int((params or {}).get("startIndex",1))-1,0)
    count=min(max(int((params or {}).get("count",20)),1),100)
    return {"schemas":["urn:ietf:params:scim:api:messages:2.0:ListResponse"], "totalResults":total,"startIndex":start+1,"itemsPerPage":len(rows[start:start+count]), "Resources":rows[start:start+count]}
