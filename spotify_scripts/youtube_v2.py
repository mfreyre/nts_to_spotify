import argparse
import csv
import os
import re
import sys
import time
from urllib.parse import urlencode, quote_plus

import requests
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_BASE = 'https://www.googleapis.com/youtube/v3'

# Quota costs per operation
QUOTA_SEARCH = 100
QUOTA_INSERT_PLAYLIST = 50
QUOTA_INSERT_ITEM = 50


def read_csv_tracks(path):
    """Read a CSV with TITLE,ARTIST columns (case-insensitive)."""
    tracks = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        field_map = {name.lower(): name for name in reader.fieldnames or []}
        if 'title' not in field_map or 'artist' not in field_map:
            raise ValueError(
                f"CSV must have TITLE and ARTIST columns. Found: {reader.fieldnames}"
            )
        title_col, artist_col = field_map['title'], field_map['artist']
        for row in reader:
            title = (row.get(title_col) or '').strip()
            artist = (row.get(artist_col) or '').strip().rstrip(',')
            if title and artist:
                tracks.append({'title': title, 'artist': artist})
    return tracks


def _normalize_for_search(s):
    """Remove quotes, ampersands, and other special symbols that hurt search."""
    # Remove quotes (single, double, fancy)
    s = re.sub(r"""[\"'\u2018\u2019\u201c\u201d]""", '', s)
    # Replace ampersands with space
    s = s.replace('&', ' ')
    # Remove other special symbols that aren't useful for search
    s = re.sub(r'[^\w\s\-]', ' ', s)
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _request_with_retry(method, url, **kwargs):
    """HTTP request with retries on 429 and transient network errors."""
    kwargs.setdefault('timeout', 20)
    attempt = 0
    max_attempts = 6
    while True:
        attempt += 1
        try:
            resp = requests.request(method, url, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt >= max_attempts:
                raise
            backoff = min(2 ** attempt, 30)
            print(
                f'  network error ({type(e).__name__}), retry {attempt}/{max_attempts} '
                f'in {backoff}s...',
                flush=True,
            )
            time.sleep(backoff)
            continue
        if resp.status_code == 429:
            wait = int(resp.headers.get('Retry-After', '5'))
            print(f'  rate limited, sleeping {wait}s...', flush=True)
            time.sleep(wait + 1)
            continue
        # Detect quota exceeded (fatal)
        if resp.status_code == 403:
            try:
                errors = resp.json().get('error', {}).get('errors', [])
                for err in errors:
                    if err.get('reason') == 'quotaExceeded':
                        print(
                            '\nFATAL: YouTube API daily quota exceeded (10,000 units/day).',
                            flush=True,
                        )
                        print(
                            'Try again tomorrow or request a quota increase in Google Cloud Console.',
                            flush=True,
                        )
                        sys.exit(1)
            except (ValueError, AttributeError):
                pass
        if resp.status_code >= 500 and attempt < max_attempts:
            backoff = min(2 ** attempt, 30)
            print(
                f'  server error {resp.status_code}, retry {attempt}/{max_attempts} '
                f'in {backoff}s...',
                flush=True,
            )
            time.sleep(backoff)
            continue
        return resp


def search_video(access_token, title, artist):
    """Search YouTube for a video matching title + artist. Returns video ID or None."""
    clean_title = _normalize_for_search(title)
    clean_artist = _normalize_for_search(artist)
    query = f'{clean_title} {clean_artist}'

    resp = _request_with_retry(
        'GET',
        f'{YOUTUBE_API_BASE}/search',
        headers={'Authorization': f'Bearer {access_token}'},
        params={
            'part': 'snippet',
            'q': query,
            'type': 'video',
            'maxResults': 1,
        },
    )
    if resp.status_code != 200:
        return None

    items = resp.json().get('items', [])
    if items:
        return items[0]['id']['videoId']
    return None


def create_playlist(access_token, name, description):
    """Create a YouTube playlist. Returns the playlist ID."""
    resp = _request_with_retry(
        'POST',
        f'{YOUTUBE_API_BASE}/playlists',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        params={'part': 'snippet,status'},
        json={
            'snippet': {
                'title': name,
                'description': description,
            },
            'status': {
                'privacyStatus': 'private',
            },
        },
    )
    resp.raise_for_status()
    return resp.json()['id']


def add_video_to_playlist(access_token, playlist_id, video_id):
    """Add a single video to a playlist."""
    resp = _request_with_retry(
        'POST',
        f'{YOUTUBE_API_BASE}/playlistItems',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        params={'part': 'snippet'},
        json={
            'snippet': {
                'playlistId': playlist_id,
                'resourceId': {
                    'kind': 'youtube#video',
                    'videoId': video_id,
                },
            },
        },
    )
    if resp.status_code == 409:
        # Duplicate video in playlist — skip silently
        return
    resp.raise_for_status()


def main():
    parser = argparse.ArgumentParser(
        description='Create a YouTube playlist from a CSV with TITLE,ARTIST columns.'
    )
    parser.add_argument('--csv', required=True, help='Path to the CSV file')
    parser.add_argument('--name', required=True, help='Playlist name')
    parser.add_argument('--description', default='', help='Playlist description')
    parser.add_argument(
        '--access-token',
        default=os.getenv('YOUTUBE_ACCESS_TOKEN'),
        help='YouTube/Google access token. '
             'Can also be set via YOUTUBE_ACCESS_TOKEN env var.',
    )
    args = parser.parse_args()

    tracks = read_csv_tracks(args.csv)
    print(f'Read {len(tracks)} tracks from {args.csv}')
    if not tracks:
        print('No tracks to add. Exiting.')
        return

    access_token = args.access_token
    if not access_token:
        print('ERROR: No access token provided. Use --access-token or set YOUTUBE_ACCESS_TOKEN.')
        sys.exit(1)

    # Quota estimate
    estimated_quota = QUOTA_INSERT_PLAYLIST + len(tracks) * (QUOTA_SEARCH + QUOTA_INSERT_ITEM)
    print(f'Estimated YouTube API quota cost: ~{estimated_quota} units '
          f'(daily limit: 10,000)', flush=True)
    if estimated_quota > 10000:
        print('WARNING: This playlist may exceed the daily quota limit!', flush=True)

    print(f'Creating playlist "{args.name}"...', flush=True)
    playlist_id = create_playlist(access_token, args.name, args.description)
    playlist_url = f'https://www.youtube.com/playlist?list={playlist_id}'
    print(f'Playlist ID: {playlist_id}', flush=True)

    print(f'Searching YouTube for {len(tracks)} tracks...', flush=True)
    missing = []
    total_added = 0
    total = len(tracks)
    start = time.time()
    for i, t in enumerate(tracks, 1):
        video_id = search_video(access_token, t['title'], t['artist'])
        if video_id:
            add_video_to_playlist(access_token, playlist_id, video_id)
            total_added += 1
            status = 'FOUND    '
        else:
            missing.append(t)
            status = 'NOT FOUND'
        print(
            f'[{i}/{total}] {status} {t["title"]} - {t["artist"]}',
            flush=True,
        )
        if i % 50 == 0:
            elapsed = time.time() - start
            rate = i / elapsed if elapsed else 0
            eta = (total - i) / rate if rate else 0
            print(
                f'  --- progress: {i}/{total} '
                f'(added {total_added}, missing {len(missing)}, '
                f'{rate:.1f} tracks/s, ETA {eta:.0f}s) ---',
                flush=True,
            )

    print(
        f'\nAdded {total_added}/{len(tracks)} tracks to playlist "{args.name}".'
    )
    if missing:
        print(f'Missing {len(missing)} tracks (see log above).')
    print(f'Playlist URL: {playlist_url}')


if __name__ == '__main__':
    main()
