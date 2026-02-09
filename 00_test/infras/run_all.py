"""
Run all infrastructure tests.
Usage: python run_all.py
"""

import subprocess
import sys
from pathlib import Path

TESTS = [
    ("MinIO", "test_minio.py"),
    ("NATS", "test_nats.py"),
    ("SQLite", "test_sqlite.py"),
    ("Database Models & Repos", "test_database.py"),
    ("Storage Client", "test_storage.py"),
]


def main():
    print("=" * 60)
    print("OCR Platform - Infrastructure Tests")
    print("=" * 60)

    script_dir = Path(__file__).parent
    results = []

    for name, script in TESTS:
        print(f"\n{'='*60}")
        print(f"Running {name} tests...")
        print("=" * 60)

        script_path = script_dir / script
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(script_dir),
        )
        results.append((name, result.returncode == 0))

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} test suites passed")

    if passed == total:
        print("\n>>> All infrastructure tests passed!")
        print("Your environment is ready for development!")
        return 0
    else:
        print("\n>>> Some tests failed!")
        print("Please check the services and try again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
