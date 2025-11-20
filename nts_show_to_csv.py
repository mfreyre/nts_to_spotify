#!/usr/bin/env python3
"""
NTS Show to CSV - Complete Tracklist Extractor

This script takes an NTS Radio show name and produces a comprehensive CSV
containing all tracks from all episodes of that show.

Usage:
    python nts_show_to_csv.py <show_name> [output_csv]

Example:
    python nts_show_to_csv.py rachel-grace-almeida
    python nts_show_to_csv.py miss-modular miss_modular_complete.csv
"""

import requests
import json
import csv
import re
import sys
import logging
from bs4 import BeautifulSoup
from unidecode import unidecode
from typing import List, Dict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('nts_show_to_csv.log'),
        logging.StreamHandler()
    ]
)

def clean_string(s: str) -> str:
    """
    Clean and normalize track/artist strings.

    - Converts Unicode to ASCII
    - Converts to lowercase
    - Removes extra spaces
    - Removes "ft" and "feat" annotations
    """
    s = unidecode(s)
    s = s.lower()
    # Remove any extra spaces
    s = re.sub(r'\s+', ' ', s).strip()
    # Remove "ft" and anything that comes after it
    s = re.sub(r'\sft.*', '', s, flags=re.IGNORECASE)
    index = s.find("feat")
    if index != -1:
        s = s[:index]
    return s.strip()


def discover_episodes(show_name: str) -> List[str]:
    """
    Discover all episode URLs for a given NTS show using the NTS API.

    Args:
        show_name: The show slug (e.g., 'rachel-grace-almeida')

    Returns:
        List of full episode URLs
    """
    logging.info(f"Discovering episodes for show: {show_name}")

    offset = 0
    limit = 12
    episodes = []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    while True:
        url = f"https://www.nts.live/api/v2/shows/{show_name}/episodes?limit={limit}&offset={offset}"

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            if not results:
                break

            for result in results:
                episode_alias = result.get("episode_alias")
                if episode_alias:
                    episodes.append(episode_alias)

            logging.info(f"Found {len(results)} episodes (offset: {offset})")
            offset += limit

        except requests.RequestException as e:
            logging.error(f"Error fetching episodes at offset {offset}: {e}")
            break
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON response: {e}")
            break

    # Convert episode aliases to full URLs
    episode_urls = [
        f"https://www.nts.live/shows/{show_name}/episodes/{alias}"
        for alias in episodes
    ]

    logging.info(f"Total episodes discovered: {len(episode_urls)}")
    return episode_urls


def extract_tracks_from_episode(episode_url: str) -> List[Dict[str, str]]:
    """
    Extract track listings from a single NTS episode page.

    Args:
        episode_url: Full URL to the episode page

    Returns:
        List of dicts with 'title' and 'artist' keys
    """
    tracks = []

    try:
        response = requests.get(episode_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        episode_container = soup.find(id="episode-container")

        if not episode_container:
            logging.warning(f"No episode container found for {episode_url}")
            return tracks

        track_elements = episode_container.find_all(class_="track")

        for track_element in track_elements:
            try:
                artist_elem = track_element.find(class_="track__artist")
                title_elem = track_element.find(class_="track__title")

                if artist_elem and title_elem:
                    artist = clean_string(artist_elem.text.strip())
                    title = clean_string(title_elem.text.strip())

                    if artist and title:  # Only add if both exist
                        tracks.append({
                            'title': title,
                            'artist': artist,
                            'episode_url': episode_url
                        })
            except Exception as e:
                logging.warning(f"Error parsing track element: {e}")
                continue

        logging.info(f"Extracted {len(tracks)} tracks from {episode_url}")

    except requests.RequestException as e:
        logging.error(f"Error fetching episode {episode_url}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error processing {episode_url}: {e}")

    return tracks


def save_to_csv(tracks: List[Dict[str, str]], output_file: str):
    """
    Save tracks to a CSV file.

    Args:
        tracks: List of track dicts
        output_file: Path to output CSV file
    """
    logging.info(f"Saving {len(tracks)} tracks to {output_file}")

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["TITLE", "ARTIST", "EPISODE_URL"])

        for track in tracks:
            writer.writerow([
                track['title'],
                track['artist'],
                track['episode_url']
            ])

    logging.info(f"Successfully saved to {output_file}")


def main():
    """Main execution function."""

    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python nts_show_to_csv.py <show_name> [output_csv]")
        print("\nExample:")
        print("  python nts_show_to_csv.py rachel-grace-almeida")
        print("  python nts_show_to_csv.py miss-modular miss_modular_complete.csv")
        sys.exit(1)

    show_name = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else f"{show_name}_complete.csv"

    print(f"\n{'='*60}")
    print(f"NTS Show to CSV - Complete Tracklist Extractor")
    print(f"{'='*60}")
    print(f"Show: {show_name}")
    print(f"Output: {output_file}")
    print(f"{'='*60}\n")

    # Step 1: Discover all episodes
    print("Step 1/3: Discovering episodes...")
    episode_urls = discover_episodes(show_name)

    if not episode_urls:
        print(f"❌ No episodes found for show '{show_name}'")
        print("\nTroubleshooting:")
        print("  - Check that the show name is correct (use the URL slug)")
        print("  - Example: for 'https://www.nts.live/shows/rachel-grace-almeida'")
        print("    use 'rachel-grace-almeida'")
        sys.exit(1)

    print(f"✓ Found {len(episode_urls)} episodes\n")

    # Step 2: Extract tracks from all episodes
    print("Step 2/3: Extracting tracks from episodes...")
    all_tracks = []

    for i, episode_url in enumerate(episode_urls, 1):
        print(f"  Processing episode {i}/{len(episode_urls)}...", end='\r')
        tracks = extract_tracks_from_episode(episode_url)
        all_tracks.extend(tracks)

    print(f"\n✓ Extracted {len(all_tracks)} total tracks\n")

    if not all_tracks:
        print("⚠️  No tracks found in any episodes")
        print("\nPossible reasons:")
        print("  - Episodes may not have tracklists")
        print("  - NTS may have changed their page structure")
        sys.exit(1)

    # Step 3: Save to CSV
    print("Step 3/3: Saving to CSV...")
    save_to_csv(all_tracks, output_file)

    print(f"\n{'='*60}")
    print(f"✓ Success!")
    print(f"{'='*60}")
    print(f"Total Episodes: {len(episode_urls)}")
    print(f"Total Tracks: {len(all_tracks)}")
    print(f"Output File: {output_file}")
    print(f"Log File: nts_show_to_csv.log")
    print(f"{'='*60}\n")

    # Calculate some stats
    episodes_with_tracks = len(set(track['episode_url'] for track in all_tracks))
    avg_tracks = len(all_tracks) / episodes_with_tracks if episodes_with_tracks > 0 else 0
    print(f"Stats:")
    print(f"  Episodes with tracks: {episodes_with_tracks}/{len(episode_urls)}")
    print(f"  Average tracks per episode: {avg_tracks:.1f}")
    print()


if __name__ == "__main__":
    main()
