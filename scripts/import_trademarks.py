#!/usr/bin/env python3
"""Import USPTO trademark bulk data into Supabase PostgreSQL.

Downloads the USPTO Trademark Case Files Dataset (CSV), processes it,
and bulk-loads it into the namera.trademarks table.

Usage:
    # Set your Supabase direct connection string
    export DATABASE_URL="postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres"

    # Run the import
    python scripts/import_trademarks.py

    # Or specify a local CSV if already downloaded
    python scripts/import_trademarks.py --local-csv /path/to/case_file.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import httpx

# USPTO Bulk Data URLs (2023 dataset — latest available)
USPTO_BASE = "https://data.uspto.gov/ui/datasets/products/files/TRCFECO2/2023"
CASE_FILE_URL = f"{USPTO_BASE}/case_file.csv.zip"
OWNER_URL = f"{USPTO_BASE}/owner.csv.zip"
INTL_CLASS_URL = f"{USPTO_BASE}/intl_class.csv.zip"

# Status codes that indicate a LIVE/active trademark
LIVE_STATUS_CODES = {
    "630", "631", "632", "633", "634", "635", "636", "637", "638", "639",
    "640", "641", "642", "643", "644", "645", "646", "647", "648", "649",
    "650", "651", "652", "653", "654", "655", "656", "657", "658", "659",
    "660", "661", "662", "663", "664", "665", "666", "667", "668", "669",
    "680", "681",
    "700", "701", "702", "703", "704", "705",
    "800", "801",
}

DEAD_STATUS_CODES = {
    "600", "601", "602", "603", "604", "605", "606", "607", "608", "609",
    "610", "611", "612", "613", "614", "615", "616", "617", "618", "619",
    "710", "711", "712", "713", "714", "715", "716",
    "900", "901", "902",
}

BATCH_SIZE = 5000


def download_and_extract_csv(url: str, tmp_dir: Path) -> Path:
    """Download a zip file and extract the CSV inside."""
    zip_name = url.rsplit("/", 1)[-1]
    zip_path = tmp_dir / zip_name
    csv_name = zip_name.replace(".zip", "")
    csv_path = tmp_dir / csv_name

    if csv_path.exists():
        print(f"  Using cached: {csv_path}")
        return csv_path

    print(f"  Downloading {url} ...")
    # USPTO CloudFront requires browser User-Agent to get the actual file
    dl_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    with httpx.stream(
        "GET", url, follow_redirects=True, timeout=600, headers=dl_headers,
    ) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    mb_done = downloaded // (1024 * 1024)
                    mb_total = total // (1024 * 1024)
                    print(f"\r  [{pct:3d}%] {mb_done} MB / {mb_total} MB", end="", flush=True)
        print()

    print(f"  Extracting {zip_name} ...")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(tmp_dir)

    zip_path.unlink()
    return csv_path


def parse_date(val: str) -> str | None:
    """Parse USPTO date formats into ISO date string."""
    if not val or val.strip() in ("", ".", "0", "NaN"):
        return None
    val = val.strip().split(".")[0]  # Remove decimal part if present
    if len(val) == 8 and val.isdigit():
        return f"{val[:4]}-{val[4:6]}-{val[6:8]}"
    return None


def classify_status(code: str) -> str:
    """Map USPTO status code to our enum."""
    if code in LIVE_STATUS_CODES:
        return "live"
    if code in DEAD_STATUS_CODES:
        return "dead"
    return "pending"


def load_owners(owner_csv: Path) -> dict[str, str]:
    """Load owner names keyed by serial_number. Takes the first owner per mark."""
    print("Loading owners...")
    owners: dict[str, str] = {}
    with open(owner_csv, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sn = row.get("serial_no", "").strip()
            name = row.get("own_name", "").strip()
            if sn and name and sn not in owners:
                owners[sn] = name[:500]  # Truncate very long names
    print(f"  Loaded {len(owners):,} owners")
    return owners


def load_nice_classes(intl_class_csv: Path) -> dict[str, list[int]]:
    """Load NICE classification codes keyed by serial_number."""
    print("Loading NICE classes...")
    classes: dict[str, list[int]] = {}
    with open(intl_class_csv, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sn = row.get("serial_no", "").strip()
            cls_str = row.get("intl_class_cd", "").strip()
            if sn and cls_str:
                try:
                    cls_int = int(cls_str)
                    if 1 <= cls_int <= 45:
                        classes.setdefault(sn, []).append(cls_int)
                except ValueError:
                    pass
    print(f"  Loaded classes for {len(classes):,} marks")
    return classes


def process_and_insert(
    case_csv: Path,
    owners: dict[str, str],
    nice_classes: dict[str, list[int]],
    conn,
    live_only: bool = False,
):
    """Process case_file.csv and bulk insert into namera.trademarks."""

    print("Processing case_file and inserting...")

    # Truncate existing data for clean reload
    with conn.cursor() as cur:
        cur.execute("DELETE FROM namera.trademarks")
        cur.execute(
            "INSERT INTO namera.data_refresh_log (source, status) "
            "VALUES ('uspto_bulk_2023', 'running') RETURNING id"
        )
        refresh_id = cur.fetchone()[0]
    conn.commit()

    insert_sql = """
        INSERT INTO namera.trademarks (
            serial_number, registration_number, mark_text, mark_text_normalized,
            status, status_code, filing_date, registration_date,
            owner_name, nice_classes, mark_draw_code
        ) VALUES (
            %(serial)s, %(reg_no)s, %(mark)s, %(mark_norm)s,
            %(status)s::namera.mark_status, %(status_code)s, %(filing_dt)s, %(reg_dt)s,
            %(owner)s, %(classes)s, %(draw_code)s
        )
        ON CONFLICT (serial_number) DO UPDATE SET
            mark_text = EXCLUDED.mark_text,
            mark_text_normalized = EXCLUDED.mark_text_normalized,
            status = EXCLUDED.status,
            status_code = EXCLUDED.status_code,
            registration_date = EXCLUDED.registration_date,
            owner_name = EXCLUDED.owner_name,
            nice_classes = EXCLUDED.nice_classes,
            updated_at = now()
    """

    batch = []
    total_inserted = 0
    skipped = 0

    with open(case_csv, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            serial = row.get("serial_no", "").strip()
            mark_text = row.get("mark_id_char", "").strip()
            status_code = row.get("cfh_status_cd", "").strip()

            # Skip marks without text (design-only marks)
            if not serial or not mark_text:
                skipped += 1
                continue

            status = classify_status(status_code)

            # Optionally skip dead marks to save space
            if live_only and status == "dead":
                skipped += 1
                continue

            mark_normalized = mark_text.upper().strip()
            reg_no = row.get("registration_no", "").strip() or None
            filing_dt = parse_date(row.get("filing_dt", ""))
            reg_dt = parse_date(row.get("registration_dt", ""))
            owner = owners.get(serial)
            classes = nice_classes.get(serial, [])
            draw_code = row.get("mark_draw_cd", "").strip()[:1] or None

            batch.append({
                "serial": serial, "reg_no": reg_no,
                "mark": mark_text, "mark_norm": mark_normalized,
                "status": status, "status_code": status_code,
                "filing_dt": filing_dt, "reg_dt": reg_dt,
                "owner": owner, "classes": classes, "draw_code": draw_code,
            })

            if len(batch) >= BATCH_SIZE:
                with conn.cursor() as cur:
                    cur.executemany(insert_sql, batch)
                conn.commit()
                total_inserted += len(batch)
                msg = f"\r  Inserted {total_inserted:,} rows (skipped {skipped:,})"
                print(msg, end="", flush=True)
                batch = []

    # Insert remaining
    if batch:
        with conn.cursor() as cur:
            cur.executemany(insert_sql, batch)
        conn.commit()
        total_inserted += len(batch)

    print(f"\n  Total: {total_inserted:,} rows inserted, {skipped:,} skipped")

    # Update refresh log
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE namera.data_refresh_log SET status = 'completed', "
            "records_imported = %s, completed_at = now() WHERE id = %s",
            (total_inserted, refresh_id),
        )
    conn.commit()

    return total_inserted


def main():
    parser = argparse.ArgumentParser(description="Import USPTO trademark data into Supabase")
    parser.add_argument("--local-csv", help="Path to local case_file.csv (skip download)")
    parser.add_argument("--local-owner-csv", help="Path to local owner.csv")
    parser.add_argument("--local-intl-csv", help="Path to local intl_class.csv")
    parser.add_argument(
        "--live-only", action="store_true",
        help="Only import live/active marks (saves ~60%% space)",
    )
    parser.add_argument("--tmp-dir", help="Temp directory for downloads", default=None)
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: Set DATABASE_URL to your Supabase PostgreSQL connection string.")
        print("  Example: postgresql://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:5432/postgres")
        sys.exit(1)

    try:
        import psycopg
    except ImportError:
        print("ERROR: psycopg not installed. Run: pip install 'namera[import]'")
        sys.exit(1)

    tmp_dir = Path(args.tmp_dir) if args.tmp_dir else Path(tempfile.mkdtemp(prefix="namera_"))
    print(f"Working directory: {tmp_dir}\n")

    # Download or use local files
    if args.local_csv:
        case_csv = Path(args.local_csv)
    else:
        case_csv = download_and_extract_csv(CASE_FILE_URL, tmp_dir)

    if args.local_owner_csv:
        owner_csv = Path(args.local_owner_csv)
    else:
        owner_csv = download_and_extract_csv(OWNER_URL, tmp_dir)

    if args.local_intl_csv:
        intl_csv = Path(args.local_intl_csv)
    else:
        intl_csv = download_and_extract_csv(INTL_CLASS_URL, tmp_dir)

    # Load supporting data into memory
    owners = load_owners(owner_csv)
    nice_classes = load_nice_classes(intl_csv)

    # Connect and import
    print("\nConnecting to database...")
    conn = psycopg.connect(database_url)
    try:
        total = process_and_insert(case_csv, owners, nice_classes, conn, live_only=args.live_only)
        print(f"\nDone! {total:,} trademarks imported.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
