"""
Test API flow: login → upload files → check request status.
Run: cd 05_test_cases && python test_api_flow.py
"""

import sys
import time
import httpx

BASE_URL = "http://localhost:8080/api/v1"
EMAIL = "klinh2212112@gmail.com"
PASSWORD = "klinh2212112@gmail.com"

TEST_FILES = [
    ("data_test/1709.04109v4.pdf", "application/pdf"),
    ("data_test/29849-Article Text-33903-1-2-20240324.pdf", "application/pdf"),
    ("data_test/merrychirst.png", "image/png"),
    ("data_test/thiệp mừng năm mới.png", "image/png"),
]


def main():
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # === 1. Login ===
    print("=" * 60)
    print("[1] Login...")
    resp = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if resp.status_code != 200:
        print(f"  FAIL: {resp.status_code} - {resp.text}")
        sys.exit(1)
    token = resp.json()["token"]
    print(f"  OK: token = {token[:20]}...")
    client.headers["Authorization"] = f"Bearer {token}"

    # === 2. Check services ===
    print("\n[2] Check available services...")
    resp = client.get("/services/available")
    if resp.status_code == 200:
        services = resp.json()
        print(f"  Services: {services}")
    else:
        print(f"  WARN: {resp.status_code} - {resp.text}")

    # === 3. Upload each file individually ===
    request_ids = []
    for file_path, mime_type in TEST_FILES:
        print(f"\n[3] Upload: {file_path}")
        try:
            with open(file_path, "rb") as f:
                resp = client.post(
                    "/upload",
                    files=[("files", (file_path.split("/")[-1], f, mime_type))],
                    data={
                        "output_format": "json",
                        "method": "structured_extract",
                        "tier": "0",
                        "retention_hours": "168",
                    },
                )
            if resp.status_code == 200:
                data = resp.json()
                req_id = data["request_id"]
                request_ids.append(req_id)
                print(f"  OK: request_id={req_id}, status={data['status']}, files={data['total_files']}")
            else:
                print(f"  FAIL: {resp.status_code} - {resp.text}")
        except FileNotFoundError:
            print(f"  SKIP: file not found")
        except Exception as e:
            print(f"  ERROR: {e}")

    if not request_ids:
        print("\nNo uploads succeeded. Exiting.")
        sys.exit(1)

    # === 4. Poll request status ===
    print(f"\n[4] Polling {len(request_ids)} request(s) for 60s...")
    for i in range(12):
        time.sleep(5)
        all_done = True
        for req_id in request_ids:
            resp = client.get(f"/requests/{req_id}")
            if resp.status_code == 200:
                data = resp.json()
                status = data["status"]
                completed = data.get("completed_files", 0)
                failed = data.get("failed_files", 0)
                total = data.get("total_files", 0)
                jobs_info = ""
                if "jobs" in data:
                    job_statuses = [f"{j['status']}" for j in data["jobs"]]
                    jobs_info = f" jobs=[{', '.join(job_statuses)}]"
                print(f"  [{(i+1)*5}s] {req_id[:12]}... status={status} ({completed}/{total} done, {failed} failed){jobs_info}")
                if status in ("PROCESSING", "QUEUED"):
                    all_done = False
            else:
                print(f"  [{(i+1)*5}s] {req_id[:12]}... ERROR {resp.status_code}")
                all_done = False

        if all_done:
            print("\nAll requests finished!")
            break
    else:
        print("\nTimeout - some requests still processing.")

    # === 5. Summary ===
    print("\n" + "=" * 60)
    print("[5] Final Summary:")
    for req_id in request_ids:
        resp = client.get(f"/requests/{req_id}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  {req_id[:12]}... => {data['status']} (completed={data.get('completed_files',0)}, failed={data.get('failed_files',0)})")
        else:
            print(f"  {req_id[:12]}... => ERROR {resp.status_code}")

    client.close()


if __name__ == "__main__":
    main()
