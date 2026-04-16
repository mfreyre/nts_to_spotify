# nts-to-spotify web UI

Browser UI that kicks off the project's Python scripts:

- Generate CSVs from NTS (single episode / full show / per-episode)
- CSV -> Spotify playlist (with streaming logs)

## Setup

```
cd web
npm install
```

Requires Node >= 18 and the Python deps from `../requirements.txt` already
installed (the server shells out to `python3`).

## Spotify OAuth

The server runs on port **4200** so your Spotify app's redirect URI needs to
include:

```
http://127.0.0.1:4200/callback
```

That value must also be in `../.env` as `SPOTIFY_REDIRECT_URI`.

## Run

```
npm start
```

Then open http://127.0.0.1:4200 in a browser. Click **Connect Spotify** once
to authorize, then pick a CSV + name and hit **Build Playlist**.
