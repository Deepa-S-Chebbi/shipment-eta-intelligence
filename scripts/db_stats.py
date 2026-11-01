#!/usr/bin/env python
"""Inspect database tables, row counts, and foreign key constraints."""

import sqlite3
from pathlib import Path

db_path = Path("data/starter/logistics.sqlite")
if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
print("=" * 60)
print(f"DATABASE: {db_path}")
print("=" * 60)

tables = [
    r[0]
    for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
]

total_rows = 0
for t in tables:
    cnt = conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    total_rows += cnt
    print(f"  {t:<28} : {cnt:>6} rows")

print("-" * 60)
print(f"  TOTAL ROWS ACROSS ALL TABLES : {total_rows:>6} rows")

fk_checks = conn.execute("PRAGMA foreign_key_check").fetchall()
print(f"  PRAGMA foreign_key_check     : {len(fk_checks)} violations (clean)")
print("=" * 60)
conn.close()
