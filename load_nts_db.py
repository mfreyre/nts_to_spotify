import os
import csv
import re
from datetime import datetime
import psycopg2

DATA_DIR = os.path.join(os.path.dirname(__file__), ".scratch", "the-breakfast-show-flo")

DB_CONFIG = {
    "host": "localhost",
    "port": 7433,
    "user": "omni",
    "password": "omni",
    "dbname": "nts",
}

MONTH_MAP = {
    "january": 1, "janaury": 1,  # typo in some filenames
    "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

# Match patterns like "8th-november-2021" at the end of the filename stem
DATE_RE = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)-(\w+)-(\d{4})$"
)


def parse_filename(filename):
    """Parse a CSV filename to extract show_date and episode_title."""
    stem = filename.removesuffix(".csv")

    m = DATE_RE.search(stem)
    if not m:
        return None, stem  # fallback: no date, use full stem as title

    day, month_str, year = m.group(1), m.group(2).lower(), m.group(3)
    month = MONTH_MAP.get(month_str)
    if month is None:
        return None, stem

    show_date = datetime(int(year), month, int(day)).date()

    # Episode title is the full stem with hyphens replaced by spaces, title-cased
    episode_title = stem.replace("-", " ").title()

    return show_date, episode_title


def load_csv(filepath):
    """Read a CSV and return list of (dj, show, title, artist) rows."""
    rows = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((
                row.get("DJ", "").strip(),
                row.get("SHOW", "").strip(),
                row.get("TITLE", "").strip(),
                row.get("ARTIST", "").strip(),
            ))
    return rows


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    files = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".csv"))
    total_rows = 0

    for filename in files:
        filepath = os.path.join(DATA_DIR, filename)
        show_date, episode_title = parse_filename(filename)
        rows = load_csv(filepath)

        for dj, show, song, artist in rows:
            cur.execute(
                """
                INSERT INTO "nts info" (show_date, episode_title, show, dj_name, song_name, artist_name)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (show_date, episode_title, show, dj, song, artist),
            )
            total_rows += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Loaded {total_rows} rows from {len(files)} files.")


if __name__ == "__main__":
    main()
