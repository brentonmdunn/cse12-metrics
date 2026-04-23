#!/usr/bin/env python3
"""Query the cse12-metrics API from a local machine.

Usage:
  python client.py                                                     # latest submission per student (default)
  python client.py --assignment-id hw3 --question-num 1               # tokens per student for a specific question
  python client.py --all                                               # all raw events
  python client.py --student-uuid <uuid>                               # raw events filtered by student UUID
  python client.py --student-uuid <uuid> --submission-num 5           # single submission events

Env vars (or pass as flags):
  METRICS_URL     base URL of the API   (default: http://localhost:8000)
  METRICS_API_KEY your API key
"""

import argparse
import json
import os
import sys
import urllib.request
from urllib.parse import urlencode


def fetch(url: str, api_key: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"X-API-Key": api_key})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()}")
    except urllib.error.URLError as e:
        sys.exit(f"Connection error: {e.reason}")


def print_table(rows: list[dict], columns: list[str]) -> None:
    if not rows:
        print("(no results)")
        return
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            widths[col] = max(widths[col], len(str(row.get(col, ""))))
    header = "  ".join(col.ljust(widths[col]) for col in columns)
    separator = "  ".join("-" * widths[col] for col in columns)
    print(header)
    print(separator)
    for row in rows:
        print("  ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns))


def main() -> None:
    parser = argparse.ArgumentParser(description="cse12-metrics client")
    parser.add_argument("--url", default=os.environ.get("METRICS_URL", "http://localhost:8000"),
                        help="API base URL")
    parser.add_argument("--key", default=os.environ.get("METRICS_API_KEY"),
                        help="API key (or set METRICS_API_KEY)")
    parser.add_argument("--student-uuid", dest="student_uuid", help="Filter raw events by student UUID")
    parser.add_argument("--submission-num", type=int, dest="submission_num",
                        help="Filter raw events by submission_num")
    parser.add_argument("--grading-run", type=int, dest="grading_run",
                        help="Filter raw events by grading_run")
    parser.add_argument("--assignment-id", dest="assignment_id",
                        help="Assignment ID for by-question query (requires --question-num)")
    parser.add_argument("--question-num", type=int, dest="question_num",
                        help="Question number for by-question query (requires --assignment-id)")
    parser.add_argument("--all", action="store_true", dest="all_events",
                        help="Show all raw events instead of latest-per-name summary")
    args = parser.parse_args()

    if not args.key:
        sys.exit("Error: set METRICS_API_KEY env var or pass --key")

    if bool(args.assignment_id) != bool(args.question_num is not None):
        sys.exit("Error: --assignment-id and --question-num must be used together")

    base = args.url.rstrip("/")

    if args.assignment_id and args.question_num is not None:
        params = {"assignment_id": args.assignment_id, "question_num": args.question_num}
        rows = fetch(f"{base}/metrics/usage/by-question?{urlencode(params)}", args.key)
        print_table(rows, ["student_uuid", "submission_num", "grading_run", "input_tokens", "output_tokens"])
        return

    raw_mode = args.all_events or args.student_uuid or args.submission_num is not None or args.grading_run is not None

    if raw_mode:
        params: dict = {}
        if args.student_uuid:
            params["student_uuid"] = args.student_uuid
        if args.submission_num is not None:
            params["submission_num"] = args.submission_num
        if args.grading_run is not None:
            params["grading_run"] = args.grading_run
        url = f"{base}/metrics/usage" + (f"?{urlencode(params)}" if params else "")
        rows = fetch(url, args.key)
        print_table(rows, ["student_uuid", "submission_num", "assignment_id", "question_num",
                            "grading_run", "input_tokens", "output_tokens", "created_at"])
    else:
        rows = fetch(f"{base}/metrics/usage/latest-per-student", args.key)
        print_table(rows, ["student_uuid", "submission_num", "input_tokens",
                            "output_tokens", "total_tokens"])


if __name__ == "__main__":
    main()
