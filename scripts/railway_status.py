"""Railway 배포 상태 조회 — 최근 5개 + 서비스 현황"""
import json
import httpx

PROJECT_ID = "36a78a1c-ca46-4ed2-ba9a-ceb64e806647"
ENV_ID = "f8251947-3685-4c55-90e4-0900cef37463"
SERVICE_ID = "be362de3-0b00-4ccf-a7c6-946ff4d9c287"
ENV_FILE = "D:/0_Dotcell/.env.global"


def load_env(path):
    result = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            result[k] = v
    return result


def call(query, variables, token):
    r = httpx.post(
        "https://backboard.railway.com/graphql/v2",
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=60,
    )
    return r.json()


if __name__ == "__main__":
    env = load_env(ENV_FILE)
    token = env.get("RAILWAY_TOKEN", "")

    q = """
    query($projectId: String!, $serviceId: String!, $environmentId: String!) {
      deployments(
        first: 5
        input: { projectId: $projectId, serviceId: $serviceId, environmentId: $environmentId }
      ) {
        edges {
          node {
            id
            status
            createdAt
            staticUrl
            meta
            canRedeploy
            canRollback
          }
        }
      }
    }
    """
    r = call(q, {
        "projectId": PROJECT_ID,
        "serviceId": SERVICE_ID,
        "environmentId": ENV_ID,
    }, token)
    print(json.dumps(r, indent=2, ensure_ascii=False))
