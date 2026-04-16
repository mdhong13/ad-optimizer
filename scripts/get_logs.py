"""Railway 최근 배포 로그 조회"""
import httpx
import json

TOKEN = "01e95e8d-f73c-4fc9-a048-cea9b47d47ae"
PROJECT_ID = "36a78a1c-ca46-4ed2-ba9a-ceb64e806647"
ENV_ID = "f8251947-3685-4c55-90e4-0900cef37463"
SERVICE_ID = "be362de3-0b00-4ccf-a7c6-946ff4d9c287"

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
URL = "https://backboard.railway.com/graphql/v2"


def gql(query, variables=None):
    r = httpx.post(URL, json={"query": query, "variables": variables or {}}, headers=HEADERS, timeout=30)
    return r.json()


# 1. 최근 배포 목록
q = """
query($projectId: String!, $environmentId: String!, $serviceId: String!) {
  deployments(
    first: 3
    input: { projectId: $projectId, environmentId: $environmentId, serviceId: $serviceId }
  ) {
    edges { node { id status createdAt staticUrl } }
  }
}
"""
res = gql(q, {"projectId": PROJECT_ID, "environmentId": ENV_ID, "serviceId": SERVICE_ID})
print("=== Deployments ===")
print(json.dumps(res, indent=2))

deps = res.get("data", {}).get("deployments", {}).get("edges", [])
if not deps:
    exit()

dep_id = deps[0]["node"]["id"]
print(f"\n=== Logs for {dep_id} ===")

q2 = """
query($deploymentId: String!) {
  deploymentLogs(deploymentId: $deploymentId, limit: 200) {
    message severity timestamp
  }
}
"""
res2 = gql(q2, {"deploymentId": dep_id})
logs = res2.get("data", {}).get("deploymentLogs", []) or []
# errors 만
for log in logs[-80:]:
    msg = log.get("message", "")
    sev = log.get("severity", "")
    print(f"[{sev}] {msg}")
