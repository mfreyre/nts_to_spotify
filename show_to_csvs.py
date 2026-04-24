#!/usr/bin/env python3
"""
NTS Show to Per-Episode CSVs

Takes an NTS show URL or show slug and creates a directory containing
one CSV per episode, each with DJ name, show name, song title, and artist.

Usage:
    python show_to_csvs.py <show_url_or_slug>

Examples:
    python show_to_csvs.py https://www.nts.live/shows/the-breakfast-show-flo
    python show_to_csvs.py the-breakfast-show-flo
"""

import requests
import csv
import re
import sys
import os
import logging
from bs4 import BeautifulSoup
from unidecode import unidecode
from typing import List, Dict, Tuple

SCRATCH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.scratch')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('show_to_csvs.log'),
        logging.StreamHandler()
    ]
)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def clean_string(s: str) -> str:
    """Clean and normalize track/artist strings."""
    s = unidecode(s)
    s = s.lower()
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'\sft.*', '', s, flags=re.IGNORECASE)
    index = s.find("feat")
    if index != -1:
        s = s[:index]
    return s.strip()


def extract_show_slug(input_str: str) -> str:
    """Extract the show slug from a URL or return as-is if already a slug."""
    match = re.search(r'nts\.live/shows/([^/]+)', input_str)
    if match:
        return match.group(1)
    return input_str.strip().strip('/')


def discover_episodes(show_slug: str) -> Tuple[str, List[Dict]]:
    """
    Discover all episodes for a show via the NTS API.

    Returns:
        Tuple of (show_name, list of episode dicts with 'alias' and 'name' keys)
    """
    logging.info(f"Discovering episodes for: {show_slug}")

    offset = 0
    limit = 12
    episodes = []
    show_name = None

    while True:
        url = f"https://www.nts.live/api/v2/shows/{show_slug}/episodes?limit={limit}&offset={offset}"

        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])

            if not results:
                break

            if show_name is None:
                show_name = results[0].get("name", show_slug)

            for result in results:
                alias = result.get("episode_alias")
                name = result.get("name", "")
                if alias:
                    episodes.append({"alias": alias, "name": name})

            logging.info(f"Found {len(results)} episodes (offset: {offset})")
            offset += limit

        except requests.RequestException as e:
            logging.error(f"Error fetching episodes at offset {offset}: {e}")
            break

    logging.info(f"Total episodes discovered: {len(episodes)}")
    return show_name or show_slug, episodes


def extract_tracks_from_episode(show_slug: str, episode_alias: str) -> List[Dict[str, str]]:
    """Extract track listings from a single NTS episode page."""
    tracks = []
    episode_url = f"https://www.nts.live/shows/{show_slug}/episodes/{episode_alias}"

    try:
        response = requests.get(episode_url, headers=HEADERS)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        episode_container = soup.find(id="episode-container")

        if not episode_container:
            logging.warning(f"No episode container found for {episode_alias}")
            return tracks

        track_elements = episode_container.find_all(class_="track")

        for track_element in track_elements:
            artist_elem = track_element.find(class_="track__artist")
            title_elem = track_element.find(class_="track__title")

            if artist_elem and title_elem:
                artist = clean_string(artist_elem.text.strip())
                title = clean_string(title_elem.text.strip())

                if artist and title:
                    tracks.append({'title': title, 'artist': artist})

        logging.info(f"Extracted {len(tracks)} tracks from {episode_alias}")

    except requests.RequestException as e:
        logging.error(f"Error fetching episode {episode_alias}: {e}")

    return tracks


def save_episode_csv(filepath: str, dj_name: str, show_name: str, tracks: List[Dict[str, str]]):
    """Save tracks for a single episode to CSV."""
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["DJ", "SHOW", "TITLE", "ARTIST"])
        for track in tracks:
            writer.writerow([dj_name, show_name, track['title'], track['artist']])


def main():
    if len(sys.argv) < 2:
        print("Usage: python show_to_csvs.py <show_url_or_slug>")
        print("\nExamples:")
        print("  python show_to_csvs.py https://www.nts.live/shows/the-breakfast-show-flo")
        print("  python show_to_csvs.py the-breakfast-show-flo")
        sys.exit(1)

    show_input = sys.argv[1]
    show_slug = extract_show_slug(show_input)

    print(f"\n{'='*60}")
    print(f"NTS Show to Per-Episode CSVs")
    print(f"{'='*60}")
    print(f"Show slug: {show_slug}")
    print(f"{'='*60}\n")

    # Discover episodes
    print("Discovering episodes...")
    show_name, episodes = discover_episodes(show_slug)
    dj_name = show_name  # The API "name" field is the full show name with DJ

    if not episodes:
        print(f"No episodes found for '{show_slug}'")
        sys.exit(1)

    print(f"Found {len(episodes)} episodes for: {show_name}\n")

    # Create output directory
    output_dir = os.path.join(SCRATCH_DIR, show_slug)
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}/\n")

    # Process each episode
    print("Extracting tracks per episode...")
    total_tracks = 0
    episodes_with_tracks = 0

    for i, episode in enumerate(episodes, 1):
        alias = episode["alias"]
        print(f"  [{i}/{len(episodes)}] {alias}...", end=' ')

        tracks = extract_tracks_from_episode(show_slug, alias)

        if tracks:
            filepath = os.path.join(output_dir, f"{alias}.csv")
            save_episode_csv(filepath, dj_name, show_name, tracks)
            total_tracks += len(tracks)
            episodes_with_tracks += 1
            print(f"{len(tracks)} tracks")
        else:
            print("no tracks")

    print(f"\n{'='*60}")
    print(f"Done!")
    print(f"{'='*60}")
    print(f"Show: {show_name}")
    print(f"Episodes processed: {len(episodes)}")
    print(f"Episodes with tracks: {episodes_with_tracks}")
    print(f"Total tracks: {total_tracks}")
    print(f"Output: {output_dir}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
