import argparse
import base64
import csv
import os
import sys
import time
import webbrowser
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv('SPOTIFY_CLIENT_ID')
client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:8000/callback/')


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


def _require_oauth_creds():
    if not client_id or not client_secret:
        raise ValueError(
            "Spotify credentials not found. Please create a .env file with:\n"
            "SPOTIFY_CLIENT_ID=your_client_id\n"
            "SPOTIFY_CLIENT_SECRET=your_client_secret\n"
            "See .env.example for template."
        )


def get_user_access_token():
    """Run the authorization code flow and return an access token."""
    _require_oauth_creds()
    auth_params = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'scope': 'playlist-modify-public playlist-modify-private',
    }
    auth_url = f'https://accounts.spotify.com/authorize?{urlencode(auth_params)}'

    print('Please authorize this app to access your Spotify account.')
    print('Opening browser...')
    webbrowser.open_new(auth_url)
    print(f'If the browser did not open, visit:\n{auth_url}\n')
    auth_code = input('Paste the "code" query parameter from the redirect URL: ').strip()

    auth_header = base64.b64encode(
        f'{client_id}:{client_secret}'.encode('ascii')
    ).decode('ascii')
    token_response = requests.post(
        'https://accounts.spotify.com/api/token',
        headers={'Authorization': f'Basic {auth_header}'},
        data={
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': redirect_uri,
        },
    )
    token_response.raise_for_status()
    return token_response.json()['access_token']


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
            wait = int(resp.headers.get('Retry-After', '1'))
            print(f'  rate limited, sleeping {wait}s...', flush=True)
            time.sleep(wait + 1)
            continue
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


def _search_request(access_token, query):
    return _request_with_retry(
        'GET',
        'https://api.spotify.com/v1/search',
        headers={'Authorization': f'Bearer {access_token}'},
        params={'q': query, 'type': 'track', 'limit': 1},
    )


def _normalize_for_search(s):
    """Remove quotes, ampersands, and other special symbols that hurt Spotify search."""
    import re
    # Remove quotes (single, double, fancy)
    s = re.sub(r"""[\"'\u2018\u2019\u201c\u201d]""", '', s)
    # Replace ampersands with space
    s = s.replace('&', ' ')
    # Remove other special symbols that aren't useful for search
    s = re.sub(r'[^\w\s\-]', ' ', s)
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def search_track(access_token, title, artist):
    """Return a Spotify track URI for (title, artist) or None."""
    clean_title = _normalize_for_search(title)
    clean_artist = _normalize_for_search(artist)

    if clean_title != title or clean_artist != artist:
        print(f'  normalized: "{clean_title}" - "{clean_artist}"', flush=True)

    resp = _search_request(access_token, f'track:"{clean_title}" artist:"{clean_artist}"')
    if resp.status_code == 200:
        items = resp.json().get('tracks', {}).get('items', [])
        if items:
            return items[0]['uri']

    # Fallback: loose search without field filters
    resp = _search_request(access_token, f'{clean_title} {clean_artist}')
    if resp.status_code != 200:
        return None
    items = resp.json().get('tracks', {}).get('items', [])
    return items[0]['uri'] if items else None


def create_playlist(access_token, name, description):
    me = _request_with_retry(
        'GET',
        'https://api.spotify.com/v1/me',
        headers={'Authorization': f'Bearer {access_token}'},
    )
    me.raise_for_status()
    user_id = me.json()['id']

    resp = _request_with_retry(
        'POST',
        f'https://api.spotify.com/v1/users/{user_id}/playlists',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        json={'name': name, 'description': description, 'public': False},
    )
    resp.raise_for_status()
    return resp.json()['id']


def add_tracks(access_token, playlist_id, uris):
    """Add a batch of URIs to the playlist (Spotify allows up to 100 per call)."""
    for i in range(0, len(uris), 100):
        batch = uris[i:i + 100]
        resp = _request_with_retry(
            'POST',
            f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            },
            json={'uris': batch},
        )
        resp.raise_for_status()


def main():
    parser = argparse.ArgumentParser(
        description='Create a Spotify playlist from a CSV with TITLE,ARTIST columns.'
    )
    parser.add_argument('--csv', required=True, help='Path to the CSV file')
    parser.add_argument('--name', required=True, help='Playlist name')
    parser.add_argument('--description', default='', help='Playlist description')
    parser.add_argument(
        '--access-token',
        default=os.getenv('SPOTIFY_ACCESS_TOKEN'),
        help='Spotify access token (skips interactive OAuth). '
             'Can also be set via SPOTIFY_ACCESS_TOKEN env var.',
    )
    args = parser.parse_args()

    tracks = read_csv_tracks(args.csv)
    print(f'Read {len(tracks)} tracks from {args.csv}')
    if not tracks:
        print('No tracks to add. Exiting.')
        return

    access_token = args.access_token or get_user_access_token()

    print(f'Creating playlist "{args.name}"...', flush=True)
    playlist_id = create_playlist(access_token, args.name, args.description)
    print(f'Playlist ID: {playlist_id}', flush=True)

    print(f'Searching Spotify for {len(tracks)} tracks...', flush=True)
    FLUSH_EVERY = 20
    pending, missing = [], []
    total_added = 0
    total = len(tracks)
    start = time.time()
    for i, t in enumerate(tracks, 1):
        uri = search_track(access_token, t['title'], t['artist'])
        if uri:
            pending.append(uri)
            status = 'FOUND    '
        else:
            missing.append(t)
            status = 'NOT FOUND'
        print(
            f'[{i}/{total}] {status} {t["title"]} - {t["artist"]}',
            flush=True,
        )
        if len(pending) >= FLUSH_EVERY:
            add_tracks(access_token, playlist_id, pending)
            total_added += len(pending)
            print(
                f'  --- pushed {len(pending)} tracks to playlist '
                f'(total added: {total_added}) ---',
                flush=True,
            )
            pending = []
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

    # Push any remaining tracks.
    if pending:
        add_tracks(access_token, playlist_id, pending)
        total_added += len(pending)

    print(
        f'\nAdded {total_added}/{len(tracks)} tracks to playlist "{args.name}".'
    )
    if missing:
        print(f'Missing {len(missing)} tracks (see log above).')
    print(f'Playlist URL: https://open.spotify.com/playlist/{playlist_id}')


if __name__ == '__main__':
    main()
