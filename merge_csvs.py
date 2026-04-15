#!/usr/bin/env python3
"""
Merge all per-episode CSVs from the 2026/ directory into one file.

Usage:
    python merge_csvs.py
"""

import csv
import glob
import os

INPUT_DIR = "2026"
OUTPUT_FILE = "2026_all_tracks.csv"
HEADER = ["DJ", "SHOW", "TITLE", "ARTIST"]


def main():
    csv_files = sorted(glob.glob(os.path.join(INPUT_DIR, "*.csv")))

    if not csv_files:
        print(f"No CSV files found in {INPUT_DIR}/")
        return

    total_tracks = 0

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(HEADER)

        for filepath in csv_files:
            with open(filepath, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)  # skip header
                count = 0
                for row in reader:
                    writer.writerow(row)
                    count += 1
                total_tracks += count

    print(f"Merged {len(csv_files)} files -> {OUTPUT_FILE} ({total_tracks} tracks)")


if __name__ == "__main__":
    main()
