"""
Example: Using the Truth Core Server API

This example shows how to interact with the Truth Core HTTP server programmatically
using Python requests.

Prerequisites:
    pip install requests

Start the server first:
    truthctl serve --port 8000

Then run this script:
    python server_api_example.py
"""

import json
import sys
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000"


def check_health():
    """Check if the server is running."""
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health Status: {response.json()}")
    return response.status_code == 200


def get_status():
    """Get server capabilities and status."""
    response = requests.get(f"{BASE_URL}/api/v1/status")
    data = response.json()
    print(f"\nServer Version: {data['version']}")
    print(f"Cache Enabled: {data['cache_enabled']}")
    print(f"Available Commands: {', '.join(data['commands'])}")
    return data


def run_judge(profile="base", parallel=True):
    """Run a readiness check via the API."""
    payload = {
        "profile": profile,
        "parallel": parallel,
        "sign": False,
    }

    print(f"\nRunning judge with profile '{profile}'...")
    response = requests.post(
        f"{BASE_URL}/api/v1/judge",
        json=payload
    )

    if response.status_code == 200:
        data = response.json()
        print(f"Job ID: {data['job_id']}")
        print(f"Status: {data['status']}")
        print(f"Cached: {data.get('cached', False)}")

        if "results" in data:
            print(f"Results: {json.dumps(data['results'], indent=2)}")

        return data
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None


def run_intel(mode="readiness"):
    """Run intelligence analysis via the API."""
    payload = {
        "mode": mode,
        "compact": False,
        "retention_days": 90,
    }

    print(f"\nRunning intel analysis with mode '{mode}'...")
    response = requests.post(
        f"{BASE_URL}/api/v1/intel",
        json=payload
    )

    if response.status_code == 200:
        data = response.json()
        print(f"Job ID: {data['job_id']}")
        print(f"Status: {data['status']}")

        if "scores" in data:
            print(f"Scores: {json.dumps(data['scores'], indent=2)}")

        return data
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None


def get_cache_stats():
    """Get cache statistics."""
    response = requests.get(f"{BASE_URL}/api/v1/cache/stats")

    if response.status_code == 200:
        data = response.json()
        print(f"\nCache Statistics:")
        print(f"  Enabled: {data['enabled']}")
        print(f"  Stats: {json.dumps(data.get('stats', {}), indent=2)}")
        return data
    else:
        print(f"Error getting cache stats: {response.status_code}")
        return None


def run_impact_analysis(diff_text: str, profile: str = "base"):
    """Run change impact analysis."""
    form_data = {
        "diff": diff_text,
        "profile": profile,
    }

    print(f"\nRunning impact analysis...")
    response = requests.post(
        f"{BASE_URL}/api/v1/impact",
        data=form_data
    )

    if response.status_code == 200:
        data = response.json()
        print(f"Selected Engines: {len(data['engines'])}")
        for engine in data['engines']:
            status = "✓" if engine['include'] else "✗"
            print(f"  {status} {engine['id']}: {engine['reason']}")

        print(f"\nSelected Invariants: {len(data['invariants'])}")
        for inv in data['invariants']:
            status = "✓" if inv['include'] else "✗"
            print(f"  {status} {inv['id']}: {inv['reason']}")

        return data
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None


def upload_and_judge(inputs_path: Path, profile: str = "ui"):
    """Upload files and run judge."""
    import zipfile
    import tempfile

    # Create a temporary ZIP file
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        zip_path = Path(tmp.name)

    # Create ZIP
    with zipfile.ZipFile(zip_path, "w") as zf:
        if inputs_path.is_file():
            zf.write(inputs_path, inputs_path.name)
        else:
            for file in inputs_path.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(inputs_path))

    # Upload and run
    payload = {
        "profile": profile,
        "parallel": True,
        "sign": False,
    }

    print(f"\nUploading {zip_path} and running judge...")

    with open(zip_path, "rb") as f:
        files = {"inputs": f}
        response = requests.post(
            f"{BASE_URL}/api/v1/judge",
            data=payload,
            files=files
        )

    # Clean up
    zip_path.unlink()

    if response.status_code == 200:
        data = response.json()
        print(f"Job ID: {data['job_id']}")
        print(f"Status: {data['status']}")
        return data
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None


def main():
    """Run all examples."""
    print("Truth Core Server API Example")
    print("=" * 50)

    # Check if server is running
    if not check_health():
        print("\n❌ Server is not running!")
        print("Start it with: truthctl serve --port 8000")
        sys.exit(1)

    print("\n✅ Server is healthy")

    # Get server status
    get_status()

    # Run a simple judge
    run_judge(profile="base")

    # Run impact analysis
    sample_diff = """diff --git a/src/main.py b/src/main.py
index 1234567..abcdefg 100644
--- a/src/main.py
+++ b/src/main.py
@@ -10,5 +10,5 @@ def main():
-    old_function()
+    new_function()
"""
    run_impact_analysis(sample_diff, profile="base")

    # Get cache stats
    get_cache_stats()

    print("\n" + "=" * 50)
    print("Example complete!")
    print(f"\nView the web interface at: {BASE_URL}/")
    print(f"API documentation at: {BASE_URL}/docs")


if __name__ == "__main__":
    main()
