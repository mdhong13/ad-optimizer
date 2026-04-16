"""Railway 커스텀 도메인 DNS 상태 확인"""
import httpx
import json

TOKEN = "01e95e8d-f73c-4fc9-a048-cea9b47d47ae"
PROJECT_ID = "36a78a1c-ca46-4ed2-ba9a-ceb64e806647"
ENV_ID = "f8251947-3685-4c55-90e4-0900cef37463"
SERVICE_ID = "be362de3-0b00-4ccf-a7c6-946ff4d9c287"

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
URL = "https://backboard.railway.com/graphql/v2"

q = """
query($projectId: String!, $environmentId: String!, $serviceId: String!) {
  domains(projectId: $projectId, environmentId: $environmentId, serviceId: $serviceId) {
    customDomains {
      id
      domain
      status {
        dnsRecords {
          hostlabel
          fqdn
          recordType
          requiredValue
          currentValue
          status
          purpose
          zone
        }
      }
    }
  }
}
"""
r = httpx.post(URL, json={"query": q, "variables": {
    "projectId": PROJECT_ID, "environmentId": ENV_ID, "serviceId": SERVICE_ID
}}, headers=HEADERS, timeout=30)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
