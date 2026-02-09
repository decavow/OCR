"""
Run all tests for OCR Platform.

Prerequisites:
  1. Docker services: docker-compose -f docker-compose.infra.yml up -d
  2. Backend running: cd backend && uvicorn app.main:app --port 8000
  3. For worker tests: PaddleOCR installed

Usage:
  python run_all_tests.py           # Run all tests
  python run_all_tests.py infra     # Infrastructure tests only
  python run_all_tests.py backend   # Backend API tests only
  python run_all_tests.py worker    # OCR Worker tests only
"""

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def run_infra_tests():
    """Run infrastructure tests."""
    print("\n" + "=" * 70)
    print("INFRASTRUCTURE TESTS")
    print("=" * 70)

    script = SCRIPT_DIR / "infras" / "run_all.py"
    result = subprocess.run([sys.executable, str(script)], cwd=str(SCRIPT_DIR / "infras"))
    return result.returncode == 0


def run_backend_tests():
    """Run backend API tests."""
    print("\n" + "=" * 70)
    print("BACKEND API TESTS")
    print("=" * 70)

    script = SCRIPT_DIR / "backend" / "run_tests.py"
    result = subprocess.run([sys.executable, str(script)], cwd=str(SCRIPT_DIR / "backend"))
    return result.returncode == 0


def run_worker_tests():
    """Run OCR worker tests."""
    print("\n" + "=" * 70)
    print("OCR WORKER TESTS")
    print("=" * 70)

    script = SCRIPT_DIR / "ocr_worker" / "run_tests.py"
    result = subprocess.run([sys.executable, str(script)], cwd=str(SCRIPT_DIR / "ocr_worker"))
    return result.returncode == 0


def main():
    test_filter = sys.argv[1] if len(sys.argv) > 1 else "all"

    results = []

    if test_filter in ["all", "infra", "infrastructure"]:
        results.append(("Infrastructure", run_infra_tests()))

    if test_filter in ["all", "backend", "api"]:
        results.append(("Backend API", run_backend_tests()))

    if test_filter in ["all", "worker", "ocr"]:
        results.append(("OCR Worker", run_worker_tests()))

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY - ALL TESTS")
    print("=" * 70)

    all_passed = True
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n>>> ALL TESTS PASSED!")
        return 0
    else:
        print("\n>>> SOME TESTS FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
