"""Quick test: upload paper_image.png and poll result."""
import sys, time, httpx

BASE_URL = "http://localhost:8080/api/v1"
client = httpx.Client(base_url=BASE_URL, timeout=30.0)

# 1. Login
print("=" * 60)
print("[1] Login...")
try:
    resp = client.post("/auth/login", json={"email": "klinh2212112@gmail.com", "password": "klinh2212112@gmail.com"})
    if resp.status_code != 200:
        print(f"  FAIL: {resp.status_code} - {resp.text}")
        sys.exit(1)
    token = resp.json()["token"]
    print(f"  OK: token={token[:20]}...")
    client.headers["Authorization"] = f"Bearer {token}"
except Exception as e:
    print(f"  ERROR connecting: {e}")
    sys.exit(1)

# 2. Services
print("\n[2] Services:")
resp = client.get("/services/available")
data = resp.json()
for s in data.get("items", []):
    print(f"  - {s['id']}: methods={s['allowed_methods']}, instances={s['active_instances']}")

# 3. Upload paper_image.png
print("\n[3] Upload: paper_image.png")
with open("data_test/paper_image.png", "rb") as f:
    resp = client.post(
        "/upload",
        files=[("files", ("paper_image.png", f, "image/png"))],
        data={"output_format": "json", "method": "structured_extract", "tier": "0", "retention_hours": "168"},
    )
print(f"  Status: {resp.status_code}")
if resp.status_code != 200:
    print(f"  Body: {resp.text}")
    sys.exit(1)
data = resp.json()
req_id = data["request_id"]
print(f"  OK: request_id={req_id}, status={data['status']}, files={data['total_files']}")

# 4. Poll 120s
print(f"\n[4] Polling {req_id[:12]}...")
for i in range(24):
    time.sleep(5)
    resp = client.get(f"/requests/{req_id}")
    d = resp.json()
    jobs_info = ""
    if "jobs" in d:
        jobs_info = " | " + ", ".join(f"{j['id'][:8]}:{j['status']}" for j in d["jobs"])
    print(f"  [{(i+1)*5:>3}s] {d['status']} done={d.get('completed_files',0)}/{d.get('total_files',0)} fail={d.get('failed_files',0)}{jobs_info}")
    if d["status"] not in ("PROCESSING", "QUEUED", "SUBMITTED"):
        print(f"\n=> FINAL: {d['status']}")
        if "jobs" in d:
            for j in d["jobs"]:
                print(f"   Job {j['id'][:8]}: {j['status']} err={j.get('error_message', 'none')}")
        # Try to get result
        if d["status"] == "COMPLETED" and "jobs" in d:
            for j in d["jobs"]:
                job_id = j["id"]
                print(f"\n[5] Getting result for job {job_id[:8]}...")
                r = client.get(f"/jobs/{job_id}/result")
                if r.status_code == 200:
                    result = r.json()
                    print(f"  Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
                    # Print first 500 chars of result
                    result_str = str(result)
                    print(f"  Preview: {result_str[:500]}")
                else:
                    print(f"  Result error: {r.status_code} - {r.text[:200]}")
        break
else:
    print("\nTimeout 120s")

client.close()
