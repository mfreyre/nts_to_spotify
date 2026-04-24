#!/usr/bin/env python3
"""
Synchronize track names between "nts info" and Spotify table.

Pulls distinct pairs from both tables, matches by artist, then uses
SequenceMatcher to find near-matching song names. Updates nts info.song_name
to match the canonical Spotify track_name.

Usage:
    python sync_track_names.py            # dry-run (preview changes)
    python sync_track_names.py --apply    # apply changes to database
"""

import argparse
import csv
import os
import sys
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher

import psycopg2

SCRATCH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.scratch')

DB_CONFIG = {
    "host": "localhost",
    "port": 7433,
    "user": "omni",
    "password": "omni",
    "dbname": "nts",
}

HIGH_THRESHOLD = 0.8
MED_THRESHOLD = 0.6
LOW_THRESHOLD = 0.4

# Artist similarity threshold for grouping
ARTIST_THRESHOLD = 0.5


def normalize(s):
    """Lowercase and strip a string."""
    return s.strip().lower()


def strip_accents(s):
    """Remove accents/diacritics for comparison purposes."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def sim(a, b):
    """SequenceMatcher ratio between two strings."""
    return SequenceMatcher(None, a, b).ratio()


def fetch_nts_pairs(cur):
    """Get distinct (song_name, artist_name) pairs from nts info."""
    cur.execute("""
        SELECT DISTINCT song_name, artist_name
        FROM "nts info"
        WHERE song_name IS NOT NULL AND song_name != ''
    """)
    return cur.fetchall()


def fetch_spotify_pairs(cur):
    """Get distinct (track_name, artist_names) pairs from Spotify table."""
    cur.execute("""
        SELECT DISTINCT track_name, artist_names
        FROM "The_NTS_breakfast_show_with_flo"
        WHERE track_name IS NOT NULL AND track_name != ''
    """)
    return cur.fetchall()


def fetch_exact_matches(cur):
    """Get NTS pairs that already have an exact case-insensitive match in Spotify."""
    cur.execute("""
        SELECT DISTINCT lower(n.song_name), lower(n.artist_name)
        FROM "nts info" n
        JOIN "The_NTS_breakfast_show_with_flo" s
            ON lower(n.song_name) = lower(s.track_name)
           AND lower(n.artist_name) = lower(s.artist_names)
    """)
    return set(cur.fetchall())


def find_near_matches(nts_pairs, spotify_pairs, exact_matches):
    """Find near-matches between NTS and Spotify using Python-side similarity."""
    # Build artist -> [(track, artist_original)] index for Spotify
    spotify_by_artist = defaultdict(list)
    for track, artist in spotify_pairs:
        key = normalize(artist)
        spotify_by_artist[key].append((track, artist))
        # Also index by accent-stripped version
        stripped = strip_accents(key)
        if stripped != key:
            spotify_by_artist[stripped].append((track, artist))

    # Get unique normalized artist names from Spotify for fuzzy artist matching
    spotify_artists = list(set(
        normalize(a) for _, a in spotify_pairs
    ))

    # Build NTS pairs grouped by artist for efficient lookup
    nts_by_artist = defaultdict(list)
    for song, artist in nts_pairs:
        nts_by_artist[normalize(artist)].append((song, artist))

    matches = []
    seen_nts_keys = set()

    print(f"  NTS distinct pairs: {len(nts_pairs)}")
    print(f"  Spotify distinct pairs: {len(spotify_pairs)}")
    print(f"  Already exact-matched: {len(exact_matches)}")

    processed = 0
    total_artists = len(nts_by_artist)

    for nts_artist_norm, nts_songs in nts_by_artist.items():
        processed += 1
        if processed % 500 == 0:
            print(f"  Processing artist {processed}/{total_artists}...")

        # Find candidate Spotify artists: exact match, accent-stripped match, or fuzzy
        candidate_artists = set()

        # Exact match
        if nts_artist_norm in spotify_by_artist:
            candidate_artists.add(nts_artist_norm)

        # Accent-stripped match
        stripped = strip_accents(nts_artist_norm)
        if stripped in spotify_by_artist:
            candidate_artists.add(stripped)

        # If no exact/stripped match, try fuzzy matching against Spotify artists
        if not candidate_artists:
            for sp_artist in spotify_artists:
                if sim(nts_artist_norm, sp_artist) >= ARTIST_THRESHOLD:
                    candidate_artists.add(sp_artist)
                    # Limit to avoid excessive comparisons
                    if len(candidate_artists) >= 3:
                        break

        if not candidate_artists:
            continue

        # Collect all candidate Spotify tracks
        sp_tracks = []
        for ca in candidate_artists:
            sp_tracks.extend(spotify_by_artist[ca])

        # Compare each NTS song against candidate Spotify tracks
        for nts_song, nts_artist_orig in nts_songs:
            nts_key = (normalize(nts_song), normalize(nts_artist_orig))

            # Skip if already exact-matched
            if nts_key in exact_matches:
                continue
            if nts_key in seen_nts_keys:
                continue

            best = None
            best_song_sim = 0

            nts_song_norm = normalize(nts_song)
            nts_song_stripped = strip_accents(nts_song_norm)

            for sp_track, sp_artist_orig in sp_tracks:
                sp_track_norm = normalize(sp_track)

                # Skip exact matches
                if nts_song_norm == sp_track_norm:
                    continue

                # Quick length check to avoid obviously bad matches
                len_ratio = len(nts_song_norm) / max(len(sp_track_norm), 1)
                if len_ratio < 0.3 or len_ratio > 3.0:
                    continue

                # Compute similarity (try accent-stripped first for speed)
                sp_stripped = strip_accents(sp_track_norm)
                song_similarity = sim(nts_song_stripped, sp_stripped)

                # If accent-stripped is very close, use the original for final score
                if song_similarity >= LOW_THRESHOLD:
                    song_similarity = sim(nts_song_norm, sp_track_norm)
                    # Boost if accent-stripped versions match better
                    stripped_sim = sim(nts_song_stripped, sp_stripped)
                    song_similarity = max(song_similarity, stripped_sim)

                if song_similarity >= LOW_THRESHOLD and song_similarity > best_song_sim:
                    artist_similarity = sim(nts_artist_norm, normalize(sp_artist_orig))
                    best_song_sim = song_similarity
                    best = {
                        "nts_song": nts_song,
                        "nts_artist": nts_artist_orig,
                        "spotify_track": sp_track,
                        "spotify_artist": sp_artist_orig,
                        "song_sim": round(song_similarity, 4),
                        "artist_sim": round(artist_similarity, 4),
                    }

            if best:
                seen_nts_keys.add(nts_key)
                matches.append(best)

    return matches


def classify_matches(matches):
    """Split matches into high/medium/low confidence buckets."""
    high, medium, low = [], [], []
    for m in matches:
        s = m["song_sim"]
        if s >= HIGH_THRESHOLD:
            high.append(m)
        elif s >= MED_THRESHOLD:
            medium.append(m)
        else:
            low.append(m)
    return high, medium, low


def apply_updates(cur, matches_to_apply):
    """Execute UPDATE statements for the given matches."""
    updated = 0
    for m in matches_to_apply:
        cur.execute("""
            UPDATE "nts info"
            SET song_name = %s
            WHERE lower(song_name) = %s
              AND lower(artist_name) = %s
        """, (m["spotify_track"], m["nts_song"].lower(), m["nts_artist"].lower()))
        updated += cur.rowcount
    return updated


def write_csv(filepath, matches):
    """Write matches to a CSV file."""
    fieldnames = [
        "nts_song", "spotify_track", "nts_artist", "spotify_artist",
        "song_sim", "artist_sim",
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for m in sorted(matches, key=lambda x: -x["song_sim"]):
            writer.writerow(m)


def main():
    parser = argparse.ArgumentParser(
        description="Sync NTS track names to Spotify canonical names."
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply changes (default is dry-run)"
    )
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("Fetching data from database...")
    nts_pairs = fetch_nts_pairs(cur)
    spotify_pairs = fetch_spotify_pairs(cur)
    exact_matches = fetch_exact_matches(cur)

    print("Finding near-matches...")
    matches = find_near_matches(nts_pairs, spotify_pairs, exact_matches)
    print(f"  Near-matches found: {len(matches)}")

    high, medium, low = classify_matches(matches)
    print(f"\nConfidence breakdown:")
    print(f"  High   (sim >= {HIGH_THRESHOLD}): {len(high)}")
    print(f"  Medium (sim {MED_THRESHOLD}-{HIGH_THRESHOLD}): {len(medium)}")
    print(f"  Low    (sim {LOW_THRESHOLD}-{MED_THRESHOLD}): {len(low)} (skipped)")

    to_apply = high + medium
    print(f"\nTotal corrections to apply: {len(to_apply)}")

    # Show sample changes
    if to_apply:
        print(f"\nSample changes (first 15):")
        for m in sorted(to_apply, key=lambda x: -x["song_sim"])[:15]:
            print(f'  "{m["nts_song"]}" -> "{m["spotify_track"]}"  '
                  f'[{m["nts_artist"]}] (sim: {m["song_sim"]:.2f})')

    # Write CSVs
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    report_path = os.path.join(SCRATCH_DIR, "sync_report.csv")
    review_path = os.path.join(SCRATCH_DIR, "sync_review.csv")
    write_csv(report_path, to_apply)
    print(f"\nWrote {report_path} ({len(to_apply)} changes)")

    write_csv(review_path, low)
    print(f"Wrote {review_path} ({len(low)} skipped for review)")

    if args.apply:
        print(f"\nApplying {len(to_apply)} corrections...")
        rows_updated = apply_updates(cur, to_apply)
        conn.commit()
        print(f"Done. {rows_updated} rows updated in \"nts info\".")
    else:
        print("\nDry-run mode. No changes applied. Use --apply to execute updates.")
        conn.rollback()

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
