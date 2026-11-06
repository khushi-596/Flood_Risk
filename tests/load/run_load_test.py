"""Automated load testing runner using Locust.

Executes a headless load test against the Flood Risk API and compiles
a comprehensive markdown benchmark report with RPS, p95/p99 latency, and error rate.
If the API server is not running on the target localhost port, it automatically
spawns a local Uvicorn instance, waits for readiness, executes the test, and tears down cleanly.

Usage:
    python -m tests.load.run_load_test --host http://127.0.0.1:8000 --users 15 --duration 15
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


def _is_server_ready(host: str) -> bool:
    """Check if the target server is already responsive on /v1/health."""
    try:
        url = f"{host.rstrip('/')}/v1/health"
        with urllib.request.urlopen(url, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def _wait_for_server(host: str, timeout_sec: int = 15) -> bool:
    """Poll the target server until it becomes ready or timeout occurs."""
    start = time.time()
    while time.time() - start < timeout_sec:
        if _is_server_ready(host):
            return True
        time.sleep(0.5)
    return False


def run_benchmark(host: str = "http://127.0.0.1:8000", users: int = 15, duration_sec: int = 15) -> int:
    report_dir = Path("tests/load/results")
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_prefix = str(report_dir / "perf")

    server_proc = None
    parsed = urllib.parse.urlparse(host)
    is_local = parsed.hostname in ("localhost", "127.0.0.1")

    # If local server is not running, spin up temporary Uvicorn instance
    if is_local and not _is_server_ready(host):
        port = parsed.port or 8000
        print(f"No running server detected at {host}. Spawning local Uvicorn on port {port}...")
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--host", "127.0.0.1"],
            cwd="services/api",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not _wait_for_server(host, timeout_sec=20):
            print("Failed to start local Uvicorn server within 20s.", file=sys.stderr)
            if server_proc:
                server_proc.terminate()
            return 1
        print("Local Uvicorn server is ready!")

    try:
        cmd = [
            sys.executable,
            "-m",
            "locust",
            "-f",
            "tests/load/locustfile.py",
            "--host",
            host,
            "--headless",
            "-u",
            str(users),
            "-r",
            "3",
            "--run-time",
            f"{duration_sec}s",
            "--csv",
            csv_prefix,
            "--csv-full-history",
        ]

        print(f"Launching Locust benchmark: {users} users, {duration_sec}s against {host}...")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        print(proc.stdout)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)

        # Generate summary report if CSV was produced
        stats_file = Path(f"{csv_prefix}_stats.csv")
        if stats_file.exists():
            lines = stats_file.read_text(encoding="utf-8").strip().splitlines()
            report_md = [
                "# Locust Load Test Performance Report",
                f"- **Target Host**: `{host}`",
                f"- **Simulated Users**: {users}",
                f"- **Duration**: {duration_sec} seconds",
                f"- **Generated At**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
                "",
                "## Endpoint Performance Breakdown",
                "",
                "| Method | Name | Requests | Failures | Median (ms) | 95% (ms) | 99% (ms) | Avg (ms) | RPS |",
                "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
            ]
            for line in lines[1:]:
                parts = [p.strip('"') for p in line.split(",")]
                if len(parts) >= 10 and parts[1] != "Aggregated":
                    method, name, reqs, fails = parts[0], parts[1], parts[2], parts[3]
                    avg, median = parts[5], parts[7]
                    rps = parts[9] if len(parts) > 9 else "0.0"
                    p95 = parts[11] if len(parts) > 11 else parts[8]
                    p99 = parts[12] if len(parts) > 12 else parts[9]
                    report_md.append(f"| {method} | `{name}` | {reqs} | {fails} | {median} | {p95} | {p99} | {avg} | {rps} |")

            report_path = Path("tests/load/load_test_report.md")
            report_path.write_text("\n".join(report_md) + "\n", encoding="utf-8")
            print(f"Performance report successfully generated at {report_path}")

        return proc.returncode
    finally:
        if server_proc:
            print("Tearing down temporary local Uvicorn instance...")
            server_proc.terminate()
            server_proc.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run headless Locust benchmark")
    parser.add_argument("--host", default="http://127.0.0.1:8000", help="Target API host")
    parser.add_argument("--users", type=int, default=15, help="Number of concurrent users")
    parser.add_argument("--duration", type=int, default=15, help="Duration in seconds")
    args = parser.parse_args()
    sys.exit(run_benchmark(args.host, args.users, args.duration))
