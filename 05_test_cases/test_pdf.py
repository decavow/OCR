"""Test: upload PDF and check OCR result."""
import sys, time, httpx

BASE_URL = "http://localhost:8080/api/v1"
client = httpx.Client(base_url=BASE_URL, timeout=30.0)

# Login
resp = client.post("/auth/login", json={"email": "klinh2212112@gmail.com", "password": "klinh2212112@gmail.com"})
token = resp.json()["token"]
client.headers["Authorization"] = f"Bearer {token}"
print("[1] Logged in")

# Upload PDF
print("[2] Upload: 1709.04109v4.pdf")
with open("data_test/1709.04109v4.pdf", "rb") as f:
    resp = client.post(
        "/upload",
        files=[("files", ("1709.04109v4.pdf", f, "application/pdf"))],
        data={"output_format": "json", "method": "structured_extract", "tier": "0", "retention_hours": "168"},
    )
print(f"    Status: {resp.status_code}")
if resp.status_code != 200:
    print(f"    Body: {resp.text}")
    sys.exit(1)
data = resp.json()
req_id = data["request_id"]
print(f"    request_id={req_id}, files={data['total_files']}")

# Poll 180s (PDF can be slow)
print("[3] Polling...")
for i in range(36):
    time.sleep(5)
    resp = client.get(f"/requests/{req_id}")
    d = resp.json()
    jobs = " | ".join(f"{j['id'][:8]}:{j['status']}" for j in d.get("jobs", []))
    print(f"    [{(i+1)*5:>3}s] {d['status']} done={d.get('completed_files',0)}/{d.get('total_files',0)} fail={d.get('failed_files',0)} | {jobs}")
    if d["status"] not in ("PROCESSING", "QUEUED", "SUBMITTED"):
        break
else:
    print("    Timeout 180s")

# Get result
print("[4] Result:")
resp = client.get(f"/requests/{req_id}")
d = resp.json()
print(f"    Final: {d['status']}")
if d["status"] == "COMPLETED" and d.get("jobs"):
    job_id = d["jobs"][0]["id"]
    resp = client.get(f"/jobs/{job_id}/result")
    if resp.status_code == 200:
        result = resp.json()
        pages = result.get("pages", [])
        summary = result.get("summary", {})
        print(f"    Pages: {summary.get('total_pages',0)}, Regions: {summary.get('total_regions',0)}, Tables: {summary.get('tables_found',0)}")
        # Show first 2 pages content preview
        for p in pages[:2]:
            print(f"\n    --- Page {p['page_number']} ({len(p['regions'])} regions) ---")
            for r in p["regions"][:5]:
                content = r.get("content", r.get("html", ""))[:120]
                conf = r.get("confidence", 0)
                print(f"      [{r['type']}] (conf={conf:.2f}) {content}")
            if len(p["regions"]) > 5:
                print(f"      ... +{len(p['regions'])-5} more regions")
    else:
        print(f"    Result error: {resp.status_code} {resp.text[:200]}")

client.close()
