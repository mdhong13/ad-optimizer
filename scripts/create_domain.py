"""Railway 커스텀 도메인 생성/확인"""
import httpx

TOKEN = "01e95e8d-f73c-4fc9-a048-cea9b47d47ae"
PROJECT_ID = "36a78a1c-ca46-4ed2-ba9a-ceb64e806647"
ENV_ID = "f8251947-3685-4c55-90e4-0900cef37463"
SERVICE_ID = "be362de3-0b00-4ccf-a7c6-946ff4d9c287"
DOMAIN = "adteam.onemsg.net"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}
URL = "https://backboard.railway.com/graphql/v2"


def gql(query, variables=None):
    r = httpx.post(URL, json={"query": query, "variables": variables or {}}, headers=HEADERS, timeout=30)
    return r.json()


# 0. DNSRecords 스키마 확인
print("=== DNSRecords schema ===")
qs = """
{ __type(name: "DNSRecords") { fields { name type { name kind } } } }
"""
print(gql(qs))

# 1. 현재 도메인 목록 확인
print("\n=== Current domains ===")
q = """
query($projectId: String!, $environmentId: String!, $serviceId: String!) {
  domains(projectId: $projectId, environmentId: $environmentId, serviceId: $serviceId) {
    customDomains { id domain }
    serviceDomains { id domain }
  }
}
"""
res = gql(q, {"projectId": PROJECT_ID, "environmentId": ENV_ID, "serviceId": SERVICE_ID})
print(res)

# 2. adteam.onemsg.net 이 없으면 생성
customs = res.get("data", {}).get("domains", {}).get("customDomains", []) or []
existing = [d for d in customs if d["domain"] == DOMAIN]

if existing:
    print(f"\n{DOMAIN} already exists: {existing[0]['id']}")
else:
    print(f"\n=== Creating {DOMAIN} ===")
    m = """
    mutation($input: CustomDomainCreateInput!) {
      customDomainCreate(input: $input) {
        id
        domain
      }
    }
    """
    res2 = gql(m, {"input": {
        "domain": DOMAIN,
        "projectId": PROJECT_ID,
        "environmentId": ENV_ID,
        "serviceId": SERVICE_ID,
    }})
    print(res2)
