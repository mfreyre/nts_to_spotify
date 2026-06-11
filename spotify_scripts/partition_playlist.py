"""Split a Spotify playlist into N smaller playlists (partitions).

Given a playlist link and a number of parts, fetches every track from the
source playlist and creates N new private playlists, each holding a
contiguous, near-equal slice of the original track order.
"""

import argparse
import os
import re

from spotify_v2 import (
    _request_with_retry,
    add_tracks,
    create_playlist,
    get_user_access_token,
)


def parse_playlist_id(link):
    """Accept an open.spotify.com URL, a spotify: URI, or a bare playlist ID."""
    link = link.strip()
    m = re.search(r'open\.spotify\.com/playlist/([A-Za-z0-9]+)', link)
    if m:
        return m.group(1)
    m = re.fullmatch(r'spotify:playlist:([A-Za-z0-9]+)', link)
    if m:
        return m.group(1)
    if re.fullmatch(r'[A-Za-z0-9]{22}', link):
        return link
    raise SystemExit(f'Could not parse a Spotify playlist ID from: {link}')


def fetch_playlist(access_token, playlist_id):
    """Return (name, track_uris) for the playlist, in playlist order."""
    headers = {'Authorization': f'Bearer {access_token}'}

    resp = _request_with_retry(
        'GET',
        f'https://api.spotify.com/v1/playlists/{playlist_id}',
        headers=headers,
        params={'fields': 'name'},
    )
    if resp.status_code == 404:
        raise SystemExit(
            'Playlist not found. Check the link — if it is one of your private '
            'playlists, reconnect Spotify so the token has read access.'
        )
    resp.raise_for_status()
    name = resp.json()['name']

    uris = []
    skipped = 0
    url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
    params = {'limit': 100, 'fields': 'next,items(is_local,track(uri,type))'}
    while url:
        resp = _request_with_retry('GET', url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get('items', []):
            track = item.get('track')
            # Local files and podcast episodes can't be re-added via the API.
            if not track or item.get('is_local') or track.get('type') != 'track':
                skipped += 1
                continue
            uris.append(track['uri'])
        url = data.get('next')
        params = None  # `next` already carries limit/fields/offset
        print(f'  fetched {len(uris)} tracks...', flush=True)

    if skipped:
        print(f'  skipped {skipped} local/unavailable items', flush=True)
    return name, uris


def partition(items, n):
    """Split items into n contiguous chunks whose sizes differ by at most 1."""
    base, rem = divmod(len(items), n)
    chunks, start = [], 0
    for i in range(n):
        size = base + (1 if i < rem else 0)
        chunks.append(items[start:start + size])
        start += size
    return chunks


def main():
    parser = argparse.ArgumentParser(
        description='Split a Spotify playlist into N smaller playlists.'
    )
    parser.add_argument('--playlist', required=True, help='Playlist URL, URI, or ID')
    parser.add_argument('--parts', required=True, type=int, help='Number of partitions')
    parser.add_argument(
        '--name',
        default='',
        help='Base name for the new playlists (defaults to the source playlist name)',
    )
    parser.add_argument(
        '--access-token',
        default=os.getenv('SPOTIFY_ACCESS_TOKEN'),
        help='Spotify access token (skips interactive OAuth). '
             'Can also be set via SPOTIFY_ACCESS_TOKEN env var.',
    )
    args = parser.parse_args()

    if args.parts < 2:
        raise SystemExit('--parts must be at least 2')

    playlist_id = parse_playlist_id(args.playlist)
    access_token = args.access_token or get_user_access_token()

    print(f'Fetching playlist {playlist_id}...', flush=True)
    source_name, uris = fetch_playlist(access_token, playlist_id)
    print(f'"{source_name}" has {len(uris)} tracks', flush=True)
    if not uris:
        raise SystemExit('Playlist has no tracks to partition.')

    parts = min(args.parts, len(uris))
    if parts < args.parts:
        print(
            f'Only {len(uris)} tracks — creating {parts} partitions '
            f'instead of {args.parts}.',
            flush=True,
        )

    base_name = args.name.strip() or source_name
    chunks = partition(uris, parts)
    created = []
    for i, chunk in enumerate(chunks, 1):
        name = f'{base_name} (part {i}/{parts})'
        print(f'Creating "{name}" with {len(chunk)} tracks...', flush=True)
        new_id = create_playlist(
            access_token, name, f'Part {i} of {parts} of "{source_name}"'
        )
        add_tracks(access_token, new_id, chunk)
        created.append((name, new_id))

    print(f'\nCreated {len(created)} playlists from "{source_name}":')
    for name, pid in created:
        print(f'  {name}: https://open.spotify.com/playlist/{pid}')


if __name__ == '__main__':
    main()
