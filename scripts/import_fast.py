#!/usr/bin/env python3
"""Fast import: loads only mark_text + status from case_file.csv.

Skips owner/NICE class enrichment for speed. Run via:
    doppler run --project yurivan --config dev -- python scripts/import_fast.py
"""

from __future__ import annotations

import csv
import os
import sys
import time
from pathlib import Path

import httpx

CSV_PATH = Path("/tmp/namera_import/case_file.csv")

LIVE_CODES = {
    "630", "631", "632", "633", "634", "635", "636", "637", "638", "639",
    "640", "641", "642", "643", "644", "645", "646", "647", "648", "649",
    "650", "651", "652", "653", "654", "655", "656", "657", "658", "659",
    "660", "661", "662", "663", "664", "665", "666", "667", "668", "669",
    "680", "681",
    "700", "701", "702", "703", "704", "705",
    "800", "801",
}

BATCH_SIZE = 300


def parse_date(val: str) -> str | None:
    if not val or val.strip() in ("", ".", "0", "NaN"):
        return None
    val = val.strip().split(".")[0]
    if len(val) == 8 and val.isdigit():
        return f"{val[:4]}-{val[4:6]}-{val[6:8]}"
    return None


def send_batch(client: httpx.Client, url: str, headers: dict, rows: list[dict]) -> bool:
    for attempt in range(3):
        try:
            resp = client.post(
                f"{url}/rest/v1/trademarks?on_conflict=serial_number",
                headers={**headers, "Prefer": "resolution=merge-duplicates"},
                json=rows,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                return True
            if resp.status_code == 409:
                return True  # conflict = already exists
            print(f"\n  HTTP {resp.status_code}: {resp.text[:150]}")
            return False
        except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            print(f"\n  Network error after 3 attempts: {e}")
            return False
    return False


def main():
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("ERROR: Need NEXT_PUBLIC_SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found. Run import_via_rest.py first to download.")
        sys.exit(1)

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Content-Profile": "namera",
        "Accept-Profile": "namera",
        "Accept": "application/json",
    }

    print(f"Reading {CSV_PATH} ...")
    batch: list[dict] = []
    total = 0
    skipped = 0
    errors = 0
    t0 = time.time()

    client = httpx.Client(timeout=30)
    try:
        with open(CSV_PATH, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                serial = row.get("serial_no", "").strip()
                mark = row.get("mark_id_char", "").strip()
                code = row.get("cfh_status_cd", "").strip()

                if not serial or not mark or code not in LIVE_CODES:
                    skipped += 1
                    continue

                batch.append({
                    "serial_number": serial,
                    "mark_text": mark,
                    "mark_text_normalized": mark.upper().strip(),
                    "status": "live",
                    "status_code": code,
                    "filing_date": parse_date(row.get("filing_dt", "")),
                    "registration_date": parse_date(
                        row.get("registration_dt", ""),
                    ),
                    "registration_number": (
                        row.get("registration_no", "").strip() or None
                    ),
                    "mark_draw_code": (
                        row.get("mark_draw_cd", "").strip()[:1] or None
                    ),
                })

                if len(batch) >= BATCH_SIZE:
                    if send_batch(client, url, headers, batch):
                        total += len(batch)
                    else:
                        errors += len(batch)
                    elapsed = time.time() - t0
                    rate = total / elapsed if elapsed > 0 else 0
                    print(
                        f"\r  {total:,} inserted | {skipped:,} skipped | "
                        f"{errors:,} errors | {rate:.0f} rows/s",
                        end="", flush=True,
                    )
                    batch = []

        if batch:
            if send_batch(client, url, headers, batch):
                total += len(batch)
            else:
                errors += len(batch)
    finally:
        client.close()

    elapsed = time.time() - t0
    print(f"\n\nDone in {elapsed:.0f}s: {total:,} live marks imported.")


if __name__ == "__main__":
    main()
