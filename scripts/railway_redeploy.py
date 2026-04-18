"""Railway 배포 강제 트리거 (httpx + GraphQL)"""
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
    if not token:
        print("ERROR: RAILWAY_TOKEN not found in .env.global")
        raise SystemExit(1)

    # 시도 1: deploymentTrigger — 최신 커밋으로 새 배포
    print("Attempt 1: deploymentTrigger (latest commit)")
    q1 = """
    mutation($projectId: String!, $environmentId: String!, $serviceId: String!) {
      deploymentTrigger(input: {
        projectId: $projectId,
        environmentId: $environmentId,
        serviceId: $serviceId
      }) {
        id
        status
      }
    }
    """
    r1 = call(q1, {"projectId": PROJECT_ID, "environmentId": ENV_ID, "serviceId": SERVICE_ID}, token)
    print(json.dumps(r1, indent=2, ensure_ascii=False))

    if "errors" not in r1 and r1.get("data", {}).get("deploymentTrigger"):
        print("\n✓ Deployment triggered successfully")
        raise SystemExit(0)

    # 시도 2: serviceInstanceRedeploy
    print("\nAttempt 2: serviceInstanceRedeploy")
    q2 = """
    mutation($serviceId: String!, $environmentId: String!) {
      serviceInstanceRedeploy(serviceId: $serviceId, environmentId: $environmentId)
    }
    """
    r2 = call(q2, {"serviceId": SERVICE_ID, "environmentId": ENV_ID}, token)
    print(json.dumps(r2, indent=2, ensure_ascii=False))

    if "errors" not in r2:
        print("\n✓ Redeploy triggered")
        raise SystemExit(0)

    # 시도 3: serviceInstanceDeployV2 (GitHub source)
    print("\nAttempt 3: serviceInstanceDeployV2")
    q3 = """
    mutation($serviceId: String!, $environmentId: String!) {
      serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId)
    }
    """
    r3 = call(q3, {"serviceId": SERVICE_ID, "environmentId": ENV_ID}, token)
    print(json.dumps(r3, indent=2, ensure_ascii=False))

    print("\nAll attempts done. Check Railway dashboard.")
