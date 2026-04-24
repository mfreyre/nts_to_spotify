#!/usr/bin/env python3
"""
NTS Episode to CSV - Extract tracks from a single episode URL.

Usage:
    python episode_to_csv.py <episode_url> [output_csv]

Example:
    python episode_to_csv.py https://www.nts.live/shows/56-djs/episodes/56-djs-27th-november-2025
    python episode_to_csv.py https://www.nts.live/shows/56-djs/episodes/56-djs-27th-november-2025 my_tracks.csv
"""

import requests
import csv
import re
import sys
import os
from bs4 import BeautifulSoup
from unidecode import unidecode
from typing import List, Dict

SCRATCH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.scratch')


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


def extract_tracks_from_url(episode_url: str) -> List[Dict[str, str]]:
    """
    Extract track listings from an NTS episode URL.

    Args:
        episode_url: Full URL to the episode page

    Returns:
        List of dicts with 'title' and 'artist' keys
    """
    tracks = []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(episode_url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')
    episode_container = soup.find(id="episode-container")

    if not episode_container:
        print(f"Warning: No episode container found for {episode_url}")
        return tracks

    track_elements = episode_container.find_all(class_="track")

    for track_element in track_elements:
        artist_elem = track_element.find(class_="track__artist")
        title_elem = track_element.find(class_="track__title")

        if artist_elem and title_elem:
            artist = clean_string(artist_elem.text.strip())
            title = clean_string(title_elem.text.strip())

            if artist and title:
                tracks.append({
                    'title': title,
                    'artist': artist
                })

    return tracks


def save_to_csv(tracks: List[Dict[str, str]], output_file: str):
    """Save tracks to a CSV file."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["TITLE", "ARTIST"])
        for track in tracks:
            writer.writerow([track['title'], track['artist']])
    print(f"Saved {len(tracks)} tracks to {output_file}")


def episode_to_csv(episode_url: str, output_file: str = None) -> str:
    """
    Main function to extract tracks from an NTS episode URL and save to CSV.

    Args:
        episode_url: Full NTS episode URL
        output_file: Optional output filename (auto-generated if not provided)

    Returns:
        Path to the created CSV file
    """
    # Auto-generate filename from URL if not provided
    if not output_file:
        # Extract episode name from URL
        match = re.search(r'/episodes/([^/]+)/?$', episode_url)
        if match:
            output_file = os.path.join(SCRATCH_DIR, f"{match.group(1)}.csv")
        else:
            output_file = os.path.join(SCRATCH_DIR, "nts_tracks.csv")
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

    print(f"Fetching tracks from: {episode_url}")
    tracks = extract_tracks_from_url(episode_url)

    if not tracks:
        print("No tracks found!")
        return None

    print(f"Found {len(tracks)} tracks")
    save_to_csv(tracks, output_file)

    return output_file


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python episode_to_csv.py <episode_url> [output_csv]")
        print("\nExample:")
        print("  python episode_to_csv.py https://www.nts.live/shows/56-djs/episodes/56-djs-27th-november-2025")
        sys.exit(1)

    url = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else None

    episode_to_csv(url, output)
