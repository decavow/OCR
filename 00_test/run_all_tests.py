#!/usr/bin/env python3
"""Run all unit tests for backend and worker."""

import subprocess
import sys


def main():
    args = sys.argv[1:] or ["-v", "--tb=short"]

    print("=" * 60)
    print("Running Backend Unit Tests")
    print("=" * 60)
    backend_result = subprocess.run(
        [sys.executable, "-m", "pytest", "backend/"] + args,
        cwd=str(__import__("pathlib").Path(__file__).parent),
    )

    print("\n" + "=" * 60)
    print("Running Worker Unit Tests")
    print("=" * 60)
    worker_result = subprocess.run(
        [sys.executable, "-m", "pytest", "ocr_worker/"] + args,
        cwd=str(__import__("pathlib").Path(__file__).parent),
    )

    print("\n" + "=" * 60)
    print("Running Contract & Flow Tests")
    print("=" * 60)
    contract_result = subprocess.run(
        [sys.executable, "-m", "pytest", "contract/"] + args,
        cwd=str(__import__("pathlib").Path(__file__).parent),
    )

    print("\n" + "=" * 60)
    print("Running Integration Tests")
    print("=" * 60)
    integration_result = subprocess.run(
        [sys.executable, "-m", "pytest", "integration/"] + args,
        cwd=str(__import__("pathlib").Path(__file__).parent),
    )

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Backend:     {'PASS' if backend_result.returncode == 0 else 'FAIL'}")
    print(f"Worker:      {'PASS' if worker_result.returncode == 0 else 'FAIL'}")
    print(f"Contract:    {'PASS' if contract_result.returncode == 0 else 'FAIL'}")
    print(f"Integration: {'PASS' if integration_result.returncode == 0 else 'FAIL'}")

    sys.exit(max(backend_result.returncode, worker_result.returncode,
                 contract_result.returncode, integration_result.returncode))


if __name__ == "__main__":
    main()
