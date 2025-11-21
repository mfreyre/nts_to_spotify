#!/usr/bin/env python3
"""
Track Data Enrichment Script

Enriches track CSV data with information from multiple sources:
- Spotify: Audio features, popularity, metadata
- Last.fm: Play counts, tags, listener stats
- MusicBrainz: Recording metadata, genres, release info

Usage:
    python enrich_tracks.py <input_csv> [output_csv]

Example:
    python enrich_tracks.py rachel-grace-almeida_complete.csv
    python enrich_tracks.py tracks.csv enriched_tracks.csv
"""

import requests
import csv
import sys
import time
import logging
import os
import base64
from typing import Dict, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('enrich_tracks.log'),
        logging.StreamHandler()
    ]
)

# API Configuration
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
LASTFM_API_KEY = os.getenv('LASTFM_API_KEY')

# Rate limiting delays (seconds)
SPOTIFY_DELAY = 0.1
LASTFM_DELAY = 0.2
MUSICBRAINZ_DELAY = 1.0  # MusicBrainz requires 1 req/sec

# Global token storage
spotify_token = None
spotify_token_expiry = 0


def get_spotify_token() -> Optional[str]:
    """Get Spotify access token using client credentials flow."""
    global spotify_token, spotify_token_expiry

    # Return cached token if still valid
    if spotify_token and time.time() < spotify_token_expiry:
        return spotify_token

    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        logging.warning("Spotify credentials not found. Skipping Spotify enrichment.")
        return None

    try:
        auth_header = base64.b64encode(
            f'{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}'.encode('ascii')
        ).decode('ascii')

        response = requests.post(
            'https://accounts.spotify.com/api/token',
            headers={'Authorization': f'Basic {auth_header}'},
            data={'grant_type': 'client_credentials'}
        )
        response.raise_for_status()

        data = response.json()
        spotify_token = data['access_token']
        # Set expiry to 5 minutes before actual expiry for safety
        spotify_token_expiry = time.time() + data['expires_in'] - 300

        logging.info("Successfully obtained Spotify access token")
        return spotify_token

    except Exception as e:
        logging.error(f"Failed to get Spotify token: {e}")
        return None


def search_spotify(title: str, artist: str) -> Optional[Dict]:
    """Search for a track on Spotify and return its data."""
    token = get_spotify_token()
    if not token:
        return None

    try:
        # Search for the track
        query = f"track:{title} artist:{artist}"
        response = requests.get(
            'https://api.spotify.com/v1/search',
            headers={'Authorization': f'Bearer {token}'},
            params={'q': query, 'type': 'track', 'limit': 1}
        )
        response.raise_for_status()

        data = response.json()
        tracks = data.get('tracks', {}).get('items', [])

        if not tracks:
            return None

        track = tracks[0]
        track_id = track['id']

        # Start with basic track info
        result = {
            'spotify_id': track_id,
            'spotify_popularity': track.get('popularity'),
            'spotify_duration_ms': track.get('duration_ms'),
            'spotify_explicit': track.get('explicit'),
            'spotify_preview_url': track.get('preview_url'),
            'spotify_album': track.get('album', {}).get('name'),
            'spotify_release_date': track.get('album', {}).get('release_date'),
        }

        time.sleep(SPOTIFY_DELAY)

        # Try to get audio features (optional - don't fail if this doesn't work)
        try:
            features_response = requests.get(
                f'https://api.spotify.com/v1/audio-features/{track_id}',
                headers={'Authorization': f'Bearer {token}'}
            )
            features_response.raise_for_status()
            features = features_response.json()

            # Add audio features to result
            result.update({
                'spotify_danceability': features.get('danceability'),
                'spotify_energy': features.get('energy'),
                'spotify_key': features.get('key'),
                'spotify_loudness': features.get('loudness'),
                'spotify_mode': features.get('mode'),
                'spotify_speechiness': features.get('speechiness'),
                'spotify_acousticness': features.get('acousticness'),
                'spotify_instrumentalness': features.get('instrumentalness'),
                'spotify_liveness': features.get('liveness'),
                'spotify_valence': features.get('valence'),
                'spotify_tempo': features.get('tempo'),
                'spotify_time_signature': features.get('time_signature'),
            })
        except Exception as e:
            logging.debug(f"Could not get audio features for {artist} - {title}: {e}")
            # Continue without audio features

        return result

    except Exception as e:
        logging.debug(f"Spotify search failed for {artist} - {title}: {e}")
        return None


def search_lastfm(title: str, artist: str) -> Optional[Dict]:
    """Search for a track on Last.fm and return its data."""
    if not LASTFM_API_KEY:
        return None

    try:
        response = requests.get(
            'http://ws.audioscrobbler.com/2.0/',
            params={
                'method': 'track.getInfo',
                'api_key': LASTFM_API_KEY,
                'artist': artist,
                'track': title,
                'format': 'json'
            }
        )
        response.raise_for_status()

        data = response.json()

        if 'error' in data:
            return None

        track = data.get('track', {})

        # Get top tags
        tags = track.get('toptags', {}).get('tag', [])
        tag_names = [tag['name'] for tag in tags[:5]] if isinstance(tags, list) else []

        time.sleep(LASTFM_DELAY)

        return {
            'lastfm_playcount': track.get('playcount'),
            'lastfm_listeners': track.get('listeners'),
            'lastfm_tags': '; '.join(tag_names) if tag_names else None,
            'lastfm_url': track.get('url'),
        }

    except Exception as e:
        logging.debug(f"Last.fm search failed for {artist} - {title}: {e}")
        return None


def search_musicbrainz(title: str, artist: str) -> Optional[Dict]:
    """Search for a track on MusicBrainz and return its data."""
    headers = {
        'User-Agent': 'NTSToSpotify/1.0 (https://github.com/yourusername/nts_to_spotify)',
        'Accept': 'application/json'
    }

    try:
        # Search for recording
        query = f'recording:"{title}" AND artist:"{artist}"'
        response = requests.get(
            'https://musicbrainz.org/ws/2/recording/',
            headers=headers,
            params={
                'query': query,
                'fmt': 'json',
                'limit': 1
            }
        )
        response.raise_for_status()

        data = response.json()
        recordings = data.get('recordings', [])

        if not recordings:
            return None

        recording = recordings[0]

        # Get genres/tags
        tags = recording.get('tags', [])
        tag_names = [tag['name'] for tag in tags[:5]]

        # Get first release info
        releases = recording.get('releases', [])
        first_release = releases[0] if releases else {}

        time.sleep(MUSICBRAINZ_DELAY)

        return {
            'musicbrainz_id': recording.get('id'),
            'musicbrainz_title': recording.get('title'),
            'musicbrainz_length': recording.get('length'),
            'musicbrainz_tags': '; '.join(tag_names) if tag_names else None,
            'musicbrainz_country': first_release.get('country'),
            'musicbrainz_date': first_release.get('date'),
        }

    except Exception as e:
        logging.debug(f"MusicBrainz search failed for {artist} - {title}: {e}")
        return None


def enrich_track(title: str, artist: str) -> Dict:
    """Enrich a single track with data from all sources."""
    enriched = {}

    # Spotify
    spotify_data = search_spotify(title, artist)
    if spotify_data:
        enriched.update(spotify_data)

    # Last.fm
    lastfm_data = search_lastfm(title, artist)
    if lastfm_data:
        enriched.update(lastfm_data)

    # MusicBrainz
    musicbrainz_data = search_musicbrainz(title, artist)
    if musicbrainz_data:
        enriched.update(musicbrainz_data)

    return enriched


def get_enrichment_columns() -> List[str]:
    """Return all possible enrichment column names in order."""
    return [
        # Spotify
        'spotify_id', 'spotify_popularity', 'spotify_duration_ms',
        'spotify_explicit', 'spotify_preview_url', 'spotify_album',
        'spotify_release_date', 'spotify_danceability', 'spotify_energy',
        'spotify_key', 'spotify_loudness', 'spotify_mode', 'spotify_speechiness',
        'spotify_acousticness', 'spotify_instrumentalness', 'spotify_liveness',
        'spotify_valence', 'spotify_tempo', 'spotify_time_signature',
        # Last.fm
        'lastfm_playcount', 'lastfm_listeners', 'lastfm_tags', 'lastfm_url',
        # MusicBrainz
        'musicbrainz_id', 'musicbrainz_title', 'musicbrainz_length',
        'musicbrainz_tags', 'musicbrainz_country', 'musicbrainz_date',
    ]


def main():
    """Main execution function."""

    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: python enrich_tracks.py <input_csv> [output_csv]")
        print("\nExample:")
        print("  python enrich_tracks.py rachel-grace-almeida_complete.csv")
        sys.exit(1)

    input_file = sys.argv[1]

    # Generate output filename
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        base = input_file.rsplit('.', 1)[0]
        output_file = f"{base}_enriched.csv"

    print(f"\n{'='*60}")
    print(f"Track Data Enrichment")
    print(f"{'='*60}")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    print(f"{'='*60}\n")

    # Check which APIs are available
    apis_available = []
    if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
        apis_available.append("Spotify ✓")
    else:
        apis_available.append("Spotify ✗ (credentials missing)")

    if LASTFM_API_KEY:
        apis_available.append("Last.fm ✓")
    else:
        apis_available.append("Last.fm ✗ (API key missing)")

    apis_available.append("MusicBrainz ✓ (no key needed)")

    print("Data Sources:")
    for api in apis_available:
        print(f"  {api}")
    print()

    # Read input CSV
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            tracks = list(reader)
            original_columns = reader.fieldnames
    except FileNotFoundError:
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading input file: {e}")
        sys.exit(1)

    if not tracks:
        print("❌ Error: Input CSV is empty")
        sys.exit(1)

    # Check for required columns
    if 'TITLE' not in original_columns or 'ARTIST' not in original_columns:
        print("❌ Error: CSV must have TITLE and ARTIST columns")
        sys.exit(1)

    print(f"Processing {len(tracks)} tracks...\n")

    # Enrich each track
    enriched_tracks = []
    success_count = {'spotify': 0, 'lastfm': 0, 'musicbrainz': 0}

    for i, track in enumerate(tracks, 1):
        title = track.get('TITLE', '')
        artist = track.get('ARTIST', '')

        print(f"[{i}/{len(tracks)}] {artist} - {title}...", end='\r')

        enrichment = enrich_track(title, artist)

        # Track successes
        if any(k.startswith('spotify_') for k in enrichment.keys()):
            success_count['spotify'] += 1
        if any(k.startswith('lastfm_') for k in enrichment.keys()):
            success_count['lastfm'] += 1
        if any(k.startswith('musicbrainz_') for k in enrichment.keys()):
            success_count['musicbrainz'] += 1

        # Combine original and enriched data
        enriched_track = {**track, **enrichment}
        enriched_tracks.append(enriched_track)

    print(f"\n✓ Enrichment complete\n")

    # Prepare output columns
    enrichment_columns = get_enrichment_columns()
    output_columns = list(original_columns) + enrichment_columns

    # Write output CSV
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=output_columns)
            writer.writeheader()
            writer.writerows(enriched_tracks)

        print(f"{'='*60}")
        print(f"✓ Success!")
        print(f"{'='*60}")
        print(f"Total tracks: {len(tracks)}")
        print(f"Output file: {output_file}")
        print(f"\nMatch rates:")
        print(f"  Spotify: {success_count['spotify']}/{len(tracks)} ({success_count['spotify']/len(tracks)*100:.1f}%)")
        print(f"  Last.fm: {success_count['lastfm']}/{len(tracks)} ({success_count['lastfm']/len(tracks)*100:.1f}%)")
        print(f"  MusicBrainz: {success_count['musicbrainz']}/{len(tracks)} ({success_count['musicbrainz']/len(tracks)*100:.1f}%)")
        print(f"\nLog file: enrich_tracks.log")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"❌ Error writing output file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
