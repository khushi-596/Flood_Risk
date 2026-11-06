"""Automated load testing runner using Locust.

Executes a headless load test against the Flood Risk API and compiles
a comprehensive markdown benchmark report with RPS, p95/p99 latency, and error rate.

Usage:
    python -m tests.load.run_load_test --host http://localhost:8000 --users 15 --duration 15
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_benchmark(host: str = "http://localhost:8000", users: int = 15, duration_sec: int = 15) -> int:
    report_dir = Path("tests/load/results")
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_prefix = str(report_dir / "perf")

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
                avg, median, p95, p99 = parts[5], parts[7], parts[11] if len(parts) > 11 else parts[8], parts[12] if len(parts) > 12 else parts[9]
                rps = parts[9] if len(parts) > 9 else "0.0"
                report_md.append(f"| {method} | `{name}` | {reqs} | {fails} | {median} | {p95} | {p99} | {avg} | {rps} |")

        report_path = Path("tests/load/load_test_report.md")
        report_path.write_text("\n".join(report_md) + "\n", encoding="utf-8")
        print(f"Report generated at {report_path}")

    return proc.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run headless Locust benchmark")
    parser.add_argument("--host", default="http://localhost:8000", help="Target API host")
    parser.add_argument("--users", type=int, default=15, help="Number of concurrent users")
    parser.add_argument("--duration", type=int, default=15, help="Duration in seconds")
    args = parser.parse_args()
    sys.exit(run_benchmark(args.host, args.users, args.duration))
