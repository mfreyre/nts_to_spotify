"""Remove duplicate tracks from a Spotify playlist.

Fetches every item in the playlist and removes duplicates, keeping the first
occurrence of each track in playlist order. Two kinds of duplicates:

  * Exact duplicates  -- the same track URI appearing more than once. These are
    removed automatically.
  * Near duplicates    -- a different recording of the same song (same normalized
    title + artist, different URI), e.g. a single vs. an album version. These are
    only removed if you confirm, via the "ASK:" prompt the web UI turns into
    yes/no buttons.

Removals are done by position, highest position first, so that the positions of
the not-yet-removed items stay valid as we go (only items *after* a removed
position shift). If the job is interrupted, unique tracks are never lost.
"""

import argparse
import os
import re

from match_utils import ask_user, norm
from spotify_v2 import _request_with_retry, get_user_access_token


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


def fetch_items(access_token, playlist_id):
    """Return (name, items) where items are dicts in playlist order.

    Each item: {position, uri, title, artists}. Local files and podcast
    episodes are skipped (their positions are left untouched in the playlist).
    """
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

    items = []
    position = 0
    skipped = 0
    url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
    params = {
        'limit': 100,
        'fields': 'next,items(is_local,track(uri,type,name,artists(name)))',
    }
    while url:
        resp = _request_with_retry('GET', url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get('items', []):
            track = item.get('track')
            if not track or item.get('is_local') or track.get('type') != 'track':
                skipped += 1
                position += 1
                continue
            items.append({
                'position': position,
                'uri': track['uri'],
                'title': track.get('name', ''),
                'artists': ', '.join(a.get('name', '') for a in track.get('artists', [])),
            })
            position += 1
        url = data.get('next')
        params = None  # `next` already carries limit/fields/offset
        print(f'  fetched {len(items)} tracks...', flush=True)

    if skipped:
        print(f'  ignoring {skipped} local/unavailable items', flush=True)
    return name, items


def find_duplicates(items, check_near):
    """Return a list of positions to remove, keeping the first of each track.

    Exact-URI duplicates are always flagged. When check_near is set, a track
    whose normalized "title — artist" matches an earlier kept track but has a
    different URI is offered for removal via ask_user().
    """
    seen_uris = set()
    seen_keys = {}  # normalized "title|artist" -> kept item (for near-dup prompts)
    to_remove = []

    for item in items:
        uri = item['uri']
        key = f"{norm(item['title'])}|{norm(item['artists'])}"
        label = f"{item['title']} — {item['artists']}"

        if uri in seen_uris:
            print(f'  exact duplicate: {label}', flush=True)
            to_remove.append(item['position'])
            continue

        if check_near and key in seen_keys and seen_keys[key]['uri'] != uri:
            kept = seen_keys[key]
            if ask_user(
                f'Remove "{label}"? Looks like a duplicate of '
                f'"{kept["title"]} — {kept["artists"]}" already in the playlist'
            ):
                to_remove.append(item['position'])
                continue
            # Kept by the user — fall through and remember this URI too.

        seen_uris.add(uri)
        seen_keys.setdefault(key, item)

    return to_remove


def remove_positions(access_token, playlist_id, items, positions):
    """Remove the given playlist positions (0-based), highest first.

    Removing the highest positions first means the remaining positions never
    shift, so they stay valid across batches. Spotify allows up to 100 items
    per request.
    """
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    by_position = {it['position']: it['uri'] for it in items}
    ordered = sorted(positions, reverse=True)

    removed = 0
    for i in range(0, len(ordered), 100):
        batch = ordered[i:i + 100]
        # Group positions by URI, as the API expects: [{uri, positions:[...]}].
        grouped = {}
        for pos in batch:
            grouped.setdefault(by_position[pos], []).append(pos)
        tracks = [{'uri': uri, 'positions': pos_list} for uri, pos_list in grouped.items()]

        resp = _request_with_retry(
            'DELETE',
            f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
            headers=headers,
            json={'tracks': tracks},
        )
        resp.raise_for_status()
        removed += len(batch)
        print(f'  removed {removed}/{len(ordered)} duplicates...', flush=True)


def main():
    parser = argparse.ArgumentParser(
        description='Remove duplicate tracks from a Spotify playlist.'
    )
    parser.add_argument('--playlist', required=True, help='Playlist URL, URI, or ID')
    parser.add_argument(
        '--near-duplicates',
        action='store_true',
        help='Also offer to remove different recordings of the same song '
             '(same title + artist, different URI), confirming each one.',
    )
    parser.add_argument(
        '--access-token',
        default=os.getenv('SPOTIFY_ACCESS_TOKEN'),
        help='Spotify access token (skips interactive OAuth). '
             'Can also be set via SPOTIFY_ACCESS_TOKEN env var.',
    )
    args = parser.parse_args()

    playlist_id = parse_playlist_id(args.playlist)
    access_token = args.access_token or get_user_access_token()

    print(f'Fetching playlist {playlist_id}...', flush=True)
    name, items = fetch_items(access_token, playlist_id)
    print(f'"{name}" has {len(items)} tracks', flush=True)
    if not items:
        raise SystemExit('Playlist has no tracks to check.')

    to_remove = find_duplicates(items, args.near_duplicates)
    if not to_remove:
        print('\nNo duplicates found — playlist is already clean!')
        return

    print(f'Removing {len(to_remove)} duplicate(s) from "{name}"...', flush=True)
    remove_positions(access_token, playlist_id, items, to_remove)
    print(
        f'\nDone! Removed {len(to_remove)} duplicate(s); '
        f'{len(items) - len(to_remove)} unique tracks remain.'
    )


if __name__ == '__main__':
    main()
