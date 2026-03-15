"""E2E helpers — polling, upload, worker simulation."""

import base64
import time
import httpx


def wait_for_status(client: httpx.Client, request_id: str,
                    target_statuses: list[str],
                    timeout: int = 60, interval: float = 1.0) -> dict:
    """Poll request status until target or timeout."""
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        resp = client.get(f"/requests/{request_id}")
        if resp.status_code == 200:
            data = resp.json()
            last_status = data.get("status")
            if last_status in target_statuses:
                return data
        time.sleep(interval)
    raise TimeoutError(
        f"Request {request_id} did not reach {target_statuses} "
        f"within {timeout}s (last: {last_status})"
    )


def upload_file(client: httpx.Client, file_bytes: bytes,
                filename: str = "test.png", mime: str = "image/png",
                output_format: str = "txt", method: str = "ocr_paddle_text",
                tier: int = 0, retries: int = 3) -> httpx.Response:
    """Upload a file via multipart. Retries on rate limit (429)."""
    for attempt in range(retries):
        resp = client.post(
            "/upload",
            files=[("files", (filename, file_bytes, mime))],
            data={
                "output_format": output_format,
                "method": method,
                "tier": str(tier),
                "retention_hours": "24",
            },
        )
        if resp.status_code != 429:
            return resp
        retry_after = int(resp.headers.get("Retry-After", "3"))
        time.sleep(min(retry_after, 5))
    return resp


def upload_multiple_files(client: httpx.Client, files_data: list[tuple],
                          output_format: str = "txt",
                          method: str = "ocr_paddle_text",
                          tier: int = 0, retries: int = 3) -> httpx.Response:
    """Upload multiple files. Retries on rate limit (429)."""
    for attempt in range(retries):
        files = [("files", (name, data, mime)) for name, data, mime in files_data]
        resp = client.post(
            "/upload",
            files=files,
            data={
                "output_format": output_format,
                "method": method,
                "tier": str(tier),
                "retention_hours": "24",
            },
        )
        if resp.status_code != 429:
            return resp
        retry_after = int(resp.headers.get("Retry-After", "3"))
        time.sleep(min(retry_after, 5))
    return resp


def simulate_worker_process_job(
    client: httpx.Client,
    access_key: str,
    job_id: str,
    file_id: str,
    result_text: str = "E2E test result text",
) -> dict:
    """
    Simulate a worker processing a single job.

    Steps:
    1. Update job → PROCESSING
    2. Download file via file-proxy
    3. Upload result via file-proxy
    4. Update job → COMPLETED

    Returns dict with step results.
    """
    worker_headers = {"X-Access-Key": access_key}
    results = {}

    # Step 1: Mark PROCESSING
    resp = client.patch(
        f"/internal/jobs/{job_id}/status",
        json={"status": "PROCESSING", "engine_version": "e2e-test-1.0"},
        headers=worker_headers,
    )
    results["processing"] = {"status_code": resp.status_code, "body": resp.json()}
    assert resp.status_code == 200, f"PROCESSING update failed: {resp.text}"

    # Step 2: Download file via file-proxy
    resp = client.post(
        "/internal/file-proxy/download",
        json={"job_id": job_id, "file_id": file_id},
        headers=worker_headers,
    )
    results["download"] = {
        "status_code": resp.status_code,
        "content_length": len(resp.content),
    }
    assert resp.status_code == 200, f"File download failed: {resp.text}"

    # Step 3: Upload result via file-proxy
    result_content = base64.b64encode(result_text.encode("utf-8")).decode("ascii")
    resp = client.post(
        "/internal/file-proxy/upload",
        json={
            "job_id": job_id,
            "file_id": file_id,
            "content": result_content,
            "content_type": "text/plain",
        },
        headers=worker_headers,
    )
    results["upload"] = {"status_code": resp.status_code, "body": resp.json()}
    assert resp.status_code == 200, f"Result upload failed: {resp.text}"

    # Step 4: Mark COMPLETED
    resp = client.patch(
        f"/internal/jobs/{job_id}/status",
        json={"status": "COMPLETED", "engine_version": "e2e-test-1.0"},
        headers=worker_headers,
    )
    results["completed"] = {"status_code": resp.status_code, "body": resp.json()}
    assert resp.status_code == 200, f"COMPLETED update failed: {resp.text}"

    return results
