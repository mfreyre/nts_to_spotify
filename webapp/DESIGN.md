# Static webapp design — nts-to-spotify on GitHub Pages

This document is the build contract for `webapp/`, a **fully static** port of the
existing `web/` app (Express server + React client) so it can be hosted on GitHub
Pages with **no server at all**. Implementers: follow the contracts here exactly —
other modules are being written in parallel against these same signatures.

## Why this works statically (verified facts, do not re-litigate)

- The NTS API (`https://www.nts.live/api/v2/...`) sends `access-control-allow-origin: *`.
  Episode endpoints embed the full tracklist as JSON — no HTML scraping needed.
- The Spotify Web API and `https://accounts.spotify.com/api/token` support CORS.
  Authorization Code + PKCE needs **no client secret**, so auth runs entirely in
  the browser. The client ID is public by design.
- GitHub Pages URL will be `https://mfreyre.github.io/nts_to_spotify/` (repo is
  already public). Vite `base` is injected at build time by the Actions workflow.

## Hard constraints

- Plain JavaScript ESM (no TypeScript). React function components + hooks.
- Runtime deps: `react`, `react-dom`, `react-router-dom@6` — **nothing else**.
  Dev deps: `vite@5`, `@vitejs/plugin-react`. No axios, no papaparse, no jszip.
- 2-space indent, semicolons, single quotes — match the style of `web/client/src/`.
- Do NOT modify anything under `web/` or the Python scripts. They stay as-is.
- Only write files you own (ownership map is in your task prompt).
- Behavior parity with the Python scripts is the acceptance bar. Port logic
  faithfully, including log-line wording, thresholds, batch sizes, and ordering.
  The Python sources are the spec:
  - `spotify_scripts/spotify_v2.py` (CSV → playlist)
  - `spotify_scripts/match_utils.py` (norm/similarity/ask; ACCEPT=REJECT=0.70)
  - `spotify_scripts/partition_playlist.py`
  - `spotify_scripts/dedup_playlist.py`
  - `spotify_scripts/youtube_v2.py` (CSV → YouTube playlist)
  - `episode_to_csv.py`, `nts_show_to_csv.py`, `show_to_csvs.py` (NTS → CSV)
  - `web/client/src/**` (UI look & behavior), `web/server.js` (job/ASK protocol)

## File tree and ownership

```
webapp/
  package.json vite.config.js index.html README.md        (scaffold)
  .github → ../.github/workflows/deploy-pages.yml          (scaffold; note: repo root)
  src/
    main.jsx App.jsx styles.css usePersistentState.js      (scaffold)
    lib/
      match.js normalize.js csv.js zip.js                  (F-core)
      spotifyAuth.js spotifyApi.js                         (F-spotify)
      nts.js                                               (F-nts)
      jobs.js workspace.js                                 (F-infra)
      playlistJobs.js                                      (F-playlist)
      yt.js                                                (F-youtube)
    components/
      SettingsPanel.jsx                                    (F-spotify)
      ScrapeCard.jsx                                       (F-nts)
      LogPanel.jsx UploadZone.jsx CsvCombo.jsx             (F-infra)
      PlaylistCard.jsx PartitionCard.jsx DedupCard.jsx     (F-playlist)
  tests/
    gen_fixtures.py fixtures.json *.test.mjs               (F-core)
```

## Scaffold specifics

**package.json**: `"name": "nts-to-spotify-webapp"`, `"private": true`,
`"type": "module"`, scripts: `dev` → `vite`, `build` → `vite build`,
`preview` → `vite preview`, `test` → `node --test tests/`.
Scaffold runs `npm install` once so `package-lock.json` exists (needed by `npm ci`
in CI). Engines: node >= 18.

**vite.config.js**: react plugin; `base: process.env.VITE_BASE || '/'`.

**index.html**: same title/meta spirit as `web/client/index.html`; root div + module
script `/src/main.jsx`.

**main.jsx**: createRoot, `<HashRouter><App/></HashRouter>`, import styles.css.
HashRouter (not BrowserRouter) — GitHub Pages has no SPA fallback.

**styles.css**: port `web/client/src/styles.css` (650 lines) essentially verbatim,
then add small additional classes needed by new UI (settings panel, workspace list,
download buttons). Keep the visual identity identical.

**App.jsx**: mirror `web/client/src/App.jsx` structure: header with title, Spotify
connect button + status pill, YouTube connect button + status pill (gated on
configured), nav (scrape / playlist / partition / dedupe / settings), Routes,
shared job state, `<LogPanel job={job} />` at the bottom.

Key differences from the old App:
- Auth status comes from `getAuthState()` / `subscribeAuth()` in spotifyAuth.js
  (no `/api/auth/status` polling).
- On mount, call `completeLoginFromRedirect()` (handles `?code=...` after Spotify
  redirects back), then refresh auth state. Strip the query with
  `history.replaceState` after handling.
- `runJob` becomes: each card calls a job-starter from lib and hands the returned
  Job up via `onJob(job)`; App stores the current job and renders LogPanel.
- Routes: `/scrape` (default), `/playlist`, `/partition`, `/dedupe`, `/settings`.

**Card prop contracts** (App ↔ cards; both sides must match exactly):
```jsx
<ScrapeCard onJob={setJob} />
<PlaylistCard onJob={setJob} platform={platform} onPlatformChange={setPlatform}
              spotifyAuthed={bool} ytAuth={{ configured, connected, label, cls }}
              onConnectSpotify={fn} onConnectYouTube={fn} />
<PartitionCard onJob={setJob} spotifyAuthed={bool} onConnectSpotify={fn} />
<DedupCard onJob={setJob} spotifyAuthed={bool} onConnectSpotify={fn} />
<SettingsPanel />
<LogPanel job={jobOrNull} />
```
`platform` persists via `usePersistentState('nts.platform', 'spotify')` (port
`usePersistentState.js` from the old client verbatim).

**Root README.md** (integration agent): add a short "Static web app (GitHub Pages)"
section pointing at `webapp/README.md`. Do not rewrite the rest.

## Deploy workflow — `.github/workflows/deploy-pages.yml`

- Trigger: `push` to `main` with paths `['webapp/**', '.github/workflows/deploy-pages.yml']`,
  plus `workflow_dispatch`.
- `permissions: { contents: read, pages: write, id-token: write }`,
  `concurrency: { group: pages, cancel-in-progress: true }`.
- Steps: checkout → setup-node 20 (npm cache, `cache-dependency-path: webapp/package-lock.json`)
  → `npm ci` in `webapp/` → build with env:
  - `VITE_BASE: /${{ github.event.repository.name }}/`
  - `VITE_SPOTIFY_CLIENT_ID: ${{ vars.SPOTIFY_CLIENT_ID }}`
  - `VITE_YOUTUBE_CLIENT_ID: ${{ vars.YOUTUBE_CLIENT_ID }}`
  → `actions/configure-pages@v5` → `actions/upload-pages-artifact@v3` with
  `path: webapp/dist` → `actions/deploy-pages@v4` in a `github-pages` environment.

## Module contracts

### src/lib/normalize.js  (F-core)

```js
export function unidecodeLite(s)   // NFKD → strip combining marks → manual map
export function cleanString(s)     // port of episode_to_csv.clean_string
export function normalizeForSearch(s) // port of spotify_v2._normalize_for_search
```
- `unidecodeLite`: `s.normalize('NFKD')`, remove `\p{M}` marks, then a manual map
  for characters NFKD misses: ø→o Ø→O æ→ae Æ→AE œ→oe Œ→OE ß→ss đ→d Đ→D ł→l Ł→L
  ð→d Ð→D þ→th Þ→Th ı→i ħ→h Ħ→H ŋ→n Ŋ→N ŧ→t Ŧ→T (extend if fixtures demand).
- `cleanString`: unidecodeLite → lowercase → collapse `\s+` → strip → remove
  `/\sft.*/i` (note: applied after whitespace collapse so `.` never meets a
  newline) → truncate at first literal `feat` → trim. Order matters; match Python.
- `normalizeForSearch`: remove `["'‘’“”]` → `&`→space →
  `[^\w\s-]`→space (JS `\w` is fine post-transliteration; Python used the same
  ASCII class semantics on already-lowercased text — verify via fixtures) →
  collapse whitespace → trim.

### src/lib/match.js  (F-core)

```js
export const ACCEPT_SCORE = 0.70;
export const REJECT_SCORE = 0.70;
export function norm(s)
export function similarity(a, b)       // substring → 0.95; else SequenceMatcher ratio
export function tokenCoverage(want, got)
export function sequenceRatio(a, b)    // faithful difflib.SequenceMatcher.ratio port
```
- `sequenceRatio`: implement difflib's Ratcliff/Obershelp: recursive
  `find_longest_match` over `b2j` index, `2*matches/(len(a)+len(b))`. Skip
  autojunk (only engages at len ≥ 200; track strings are shorter — leave a comment).
  Must match Python float-for-float on the fixture set (integers in/out of the
  division, so exact equality is expected; tests may use 1e-9 tolerance).

### src/lib/csv.js  (F-core)

```js
export function parseCsv(text)             // RFC 4180: quotes, "" escapes, CRLF, fields w/ commas+newlines; strips BOM
export function parseTracksCsv(text)       // → { tracks: [{title, artist}], fields: [...] } or throws Error(msg)
export function toCsv(header, rows)        // proper quoting; \r\n not required, \n fine (match Python csv default: \r\n)
export function downloadTextFile(name, text, mime = 'text/csv')
export const TITLE_ALIASES / ARTIST_ALIASES  // exactly spotify_v2.py's tuples
```
- `parseTracksCsv` ports `read_csv_tracks`: case-insensitive alias→column pick,
  same error message shape if missing, `title.trim()`, `artist.trim()` then strip
  trailing commas (`rstrip(',')`), skip rows lacking either.
- Python's csv.DictReader keeps the FIRST occurrence of duplicate headers' last
  value — don't over-engineer; simple dict-per-row is fine.

### src/lib/zip.js  (F-core)

```js
export function makeZipBlob(files /* [{name, text}] */) // → Blob, ZIP "store" method, CRC-32, UTF-8 names
```
No compression — store entries with correct local headers + central directory.

### src/lib/spotifyAuth.js  (F-spotify)

PKCE, no secret. Storage: localStorage `nts.spotify.tokens` =
`{ accessToken, refreshToken, expiresAt }` (epoch ms, minus 30s skew like
server.js); sessionStorage `nts.spotify.pkce` = `{ verifier, state }`.

```js
export function getClientId()      // localStorage 'nts.spotify.clientId' override, else import.meta.env.VITE_SPOTIFY_CLIENT_ID, else ''
export function setClientId(id)
export function isConfigured()
export function getRedirectUri()   // location.origin + import.meta.env.BASE_URL  (e.g. https://mfreyre.github.io/nts_to_spotify/)
export async function beginLogin() // random 64-char verifier (crypto.getRandomValues), S256 challenge via crypto.subtle.digest, state nonce; navigate to accounts.spotify.com/authorize
export async function completeLoginFromRedirect() // if location.search has code (+state matches): exchange at accounts.spotify.com/api/token with code_verifier; store tokens; return true. On error throw with server message.
export async function getAccessToken()  // null if not authed; auto-refresh when within 60s of expiry (grant_type=refresh_token&client_id=...; rotate refresh token if returned)
export function getAuthState()     // { configured, authenticated, expiresAt }
export function subscribeAuth(fn)  // notify on login/logout/refresh; returns unsubscribe
export function logout()
```
Scopes (same four the server used):
`playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative`.

### src/lib/spotifyApi.js  (F-spotify)

```js
export class ApiError extends Error { status; body; }
export async function apiFetch(path, { method='GET', query, body, signal } = {})
export function parsePlaylistId(link)     // port from partition_playlist.py; throw Error with same message text
export async function searchTrack(title, artist, { signal } = {})
export async function getMe()
export async function createPlaylist(name, description)          // public: false
export async function addTracks(playlistId, uris, { signal, log } = {})  // batches of 100
export async function fetchPlaylistName(playlistId)               // 404 → throw Error(same wording as python)
export async function fetchPlaylistUris(playlistId, { log, signal }) // → { uris, skipped } — port fetch_playlist paging: limit 100, fields 'next,items(is_local,track(uri,type))', follow data.next verbatim, filter local/non-track, log '  fetched N tracks...'
export async function fetchPlaylistItems(playlistId, { log, signal }) // dedup variant with positions/title/artists; fields 'next,items(is_local,track(uri,type,name,artists(name)))'
export async function removePositions(playlistId, items, positions, { log, signal }) // DELETE /tracks, highest-first, batches of 100, grouped {uri, positions:[..]} — port remove_positions exactly
```
- `apiFetch` retry policy ports `_request_with_retry`: max 6 attempts; network
  errors and 5xx → backoff `min(2**attempt, 30)`s; **429** → wait
  `Retry-After + 1`s and retry without counting an attempt. CORS caveat: Spotify
  may not expose `Retry-After` to JS — if the header is missing, wait 2s.
  Log retry lines through an optional `log` (or silently wait; keep it simple and
  consistent). All waits must be abortable via `signal`.
- `searchTrack` ports `search_track`: normalizeForSearch both fields; first query
  `track:"T" artist:"A"`, on empty items fall back to `T A`; `limit: 5`; score
  each item `0.6*similarity(title, item.name) + 0.4*similarity(artist, joinedArtistNames)`
  (join with ', '); return best `{ uri, title, artists, score }` or null.

### src/lib/nts.js  (F-nts)

```js
export function parseNtsInput(input)
// Accepts full URLs or bare slugs:
//   .../shows/{show}/episodes/{ep}  → { type:'episode', show, episode }
//   .../shows/{show}               → { type:'show', show }
//   bare 'some-slug'                → { type:'show', show:'some-slug' }
// Port the regexes from extract_show_slug + episode URL detection in episode_to_csv.main.
export async function fetchEpisodeTracklist(show, episode, { signal } = {})
// GET https://www.nts.live/api/v2/shows/{show}/episodes/{episode}
// → json.embeds.tracklist.results: [{ artist: string, title: string, ... }]
// map through cleanString(artist)/cleanString(title); drop entries where either is empty
// → [{ title, artist }]   (cleaned, lowercase — same as the Python CSVs)
export async function discoverEpisodes(show, { log, signal } = {})
// GET .../shows/{show}/episodes?limit=24&offset=N loop; results[].episode_alias;
// metadata.resultset.count is available — use it for '(i/count)' progress logs.
// Return [aliases] in API order. Empty results → done. Non-200 → throw.
export function episodeUrl(show, alias) // https://www.nts.live/shows/{show}/episodes/{alias}
```
Verified API shapes (2026-07-06): episode json top-level has `embeds.tracklist.results`
with `artist`/`title` string fields; list endpoint has `metadata.resultset.{count,offset,limit}`
and `results[].episode_alias`; list results do NOT embed tracklists. CORS `*` on both.

### src/lib/jobs.js  (F-infra)

In-browser replacement for server.js's job registry + SSE + ASK protocol.

```js
export function createJob(name, runner) // constructs Job, starts runner immediately, returns Job
// Job shape:
// {
//   id, name,
//   lines: [{ stream: 'stdout'|'stderr'|'stdin', line }],   // append-only
//   status: 'running'|'done'|'failed'|'cancelled',
//   exitOk: bool|null,
//   pendingAsk: { question } | null,
//   subscribe(fn): unsubscribe,     // fn() called on ANY mutation (lines, status, ask)
//   answerAsk(yes: bool): void,     // resolves the pending ask; logs 'y'/'n' to stream 'stdin'
//   cancel(): void,
// }
// runner(ctx) is an async function; ctx = {
//   log(line, stream = 'stdout'),
//   ask(question): Promise<boolean>,   // logs `ASK: ${question} (y/n)` then waits for answerAsk
//   signal: AbortSignal,               // aborted by cancel()
// }
// cancel(): abort signal; a pending ask resolves false; when the runner rejects
// with an abort-flavored error, status = 'cancelled' (log '--- cancelled ---');
// other rejections: log `error: ${message}` to stderr, status 'failed';
// normal resolution: status 'done', exitOk true.
```
Subscriptions drive React re-renders (LogPanel uses `useSyncExternalStore` or a
subscribe+setState effect — implementer's choice, but no polling).

### src/lib/workspace.js  (F-infra)

In-browser CSV store (replaces the server's repo-filesystem CSV listing + uploads).
IndexedDB database `nts-webapp`, object store `csvs`.

```js
export async function listCsvs()        // [{ id, name, size, mtime, source }] newest first
export async function saveCsv(name, text, source /* 'generated'|'upload' */) // dedupe name with -2, -3… like server upload; → { id, name, size, mtime, source }
export async function getCsvText(id)    // → string (throws if missing)
export async function deleteCsv(id)
export function subscribeWorkspace(fn)  // change notifications; returns unsubscribe
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024
```

### src/lib/playlistJobs.js  (F-playlist)

Each returns the started Job from `createJob`.

```js
export function startBuildSpotifyPlaylist({ csvText, name, description })
export function startPartition({ link, parts })
export function startDedup({ link, nearDuplicates })
```
- `startBuildSpotifyPlaylist` ports spotify_v2.main faithfully: parseTracksCsv →
  `Read N tracks…`; createPlaylist first, log playlist ID; loop tracks with
  searchTrack; `FOUND`/`UNSURE` (uses `ctx.ask`, same wording)/`NOT FOUND` log lines
  with the same formats incl. `(NN% similar)`; flush pending URIs every 20 via
  addTracks with the `--- pushed … ---` line; progress line every 50 with rate/ETA;
  final summary + missing count + `Playlist URL: https://open.spotify.com/playlist/{id}`.
- `startPartition` ports partition_playlist.main: parsePlaylistId, fetch name+uris,
  `parts = min(parts, uris.length)` with the reduced-parts message, contiguous
  near-equal chunks (base+rem logic), create `${base} (part i/N)` playlists with
  description `Part i of N of "source"`, log created URLs.
- `startDedup` ports dedup_playlist.main: fetchPlaylistItems, find_duplicates port
  (exact URI dups auto; near dups via `ctx.ask` with the same question wording,
  keyed on `norm(title)|norm(artists)`), removePositions highest-first, same
  logs/summary ('No duplicates found — playlist is already clean!').
- All three check auth up front (`getAccessToken()`); if null, log a clear
  'Not authenticated with Spotify — click connect first' to stderr and fail.

### src/lib/yt.js  (F-youtube)

Port of youtube_v2.py against Google Identity Services (GIS) — browser-only,
token-model (no refresh tokens in SPAs; ~1h tokens, reconnect per session).

```js
export function getYtClientId()   // localStorage 'nts.yt.clientId' override, else import.meta.env.VITE_YOUTUBE_CLIENT_ID, else ''
export function setYtClientId(id)
export function isYtConfigured()
export async function connectYouTube()   // loads https://accounts.google.com/gsi/client once, initTokenClient({ scope: 'https://www.googleapis.com/auth/youtube' }), requestAccessToken; stores { token, expiresAt } in sessionStorage 'nts.yt.token'
export function getYtAuthState()          // { configured, authenticated }
export function subscribeYtAuth(fn)
export function startBuildYouTubePlaylist({ csvText, name, description }) // Job; port youtube_v2.py's search + playlist insert + playlistItems insert flow, incl. its matching/thresholds and log lines; surface quota errors (403 quotaExceeded) with a friendly explanation (search costs 100 units; default quota 10k/day ≈ 100 tracks)
```
Read `spotify_scripts/youtube_v2.py` first and port what it actually does — the
list above is the integration surface, not the porting spec.

### Components

- **LogPanel.jsx** (F-infra): port the old LogPanel look; render `job.lines`
  (stderr styled as error, stdin as the user's answer), autoscroll, status chip,
  a `stop` button while running (calls `job.cancel()`), and — when
  `job.pendingAsk` — the yes/no buttons the old UI rendered for `ASK:` lines,
  wired to `job.answerAsk(true|false)`.
- **UploadZone.jsx** (F-infra): port old UploadZone (drag/drop + picker) but save
  into `workspace.saveCsv(name, text, 'upload')`; enforce `.csv` + 10MB with the
  same error messages as server.js.
- **CsvCombo.jsx** (F-infra): port old CsvCombo but list from `listCsvs()`
  (subscribeWorkspace for refresh); value is the workspace id; show name, size,
  relative mtime like the old one; allow delete; expose
  `props = { value, onChange }`.
- **ScrapeCard.jsx** (F-nts): port old ScrapeCard modes: single episode → one CSV
  (`TITLE,ARTIST` header, named `{episode-alias}.csv`); whole show → one combined
  CSV (`TITLE,ARTIST,EPISODE_URL`, named `{show}_complete.csv`); whole show →
  per-episode CSVs (one per episode with `TITLE,ARTIST`, plus a
  'download all (.zip)' button via makeZipBlob). Runs as a Job (progress lines
  `Processing episode i/N …` mirroring the Python), saves results into the
  workspace, and logs `Saved N tracks to {name}`. Include a small politeness
  delay (~150ms) between episode fetches, abortable.
- **PlaylistCard.jsx / PartitionCard.jsx / DedupCard.jsx** (F-playlist): port the
  old cards' forms/validation; PlaylistCard keeps the spotify/youtube platform
  radio (YouTube disabled + dimmed when not configured, same as old), CsvCombo +
  UploadZone for source, name/description fields (persist via usePersistentState
  keys like the old app), run button starts the corresponding job and calls
  `onJob(job)`.
- **SettingsPanel.jsx** (F-spotify): new. Fields for Spotify client ID and
  YouTube client ID (get/set via the auth libs; show whether a build-time env
  default exists), read-only display of the exact redirect URI to paste into the
  Spotify dashboard, connect/disconnect buttons, and a short inline how-to.

## Testing (F-core owns; integration re-runs)

- `tests/gen_fixtures.py`: run from repo root with `python3`; imports
  `spotify_scripts/match_utils.py` (norm/similarity), `spotify_v2._normalize_for_search`,
  `episode_to_csv.clean_string`, `spotify_v2.read_csv_tracks` (via temp files),
  `partition_playlist.partition`; writes `tests/fixtures.json`. Include: accented
  unicode (é ü ø ß æ), curly quotes, feat/ft variants, ampersands, substring pairs,
  empty/whitespace strings, realistic NTS titles ("To Nkroachment: Yarbles"),
  CSVs with alias headers / quoted commas / CRLF / BOM / trailing-comma artists,
  partition cases (0..7 items × 2..5 parts — skip n> items per the job-level guard).
- `tests/*.test.mjs` (`node --test`): JS lib outputs vs fixtures (similarity to
  1e-9), plus direct unit tests for csv parse edge cases and zip structural
  sanity (PK signatures, CRC of known string).
- Commit `fixtures.json` so `npm test` needs no Python.

## User-facing docs — webapp/README.md (scaffold writes, integration finalizes)

Cover: what it is (static, no server, tokens stay in your browser); one-time setup:
1. GitHub → Settings → Pages → Source: **GitHub Actions**.
2. Spotify dashboard (developer.spotify.com) → app → add redirect URIs
   `https://mfreyre.github.io/nts_to_spotify/` and `http://127.0.0.1:5173/` (dev);
   copy the Client ID.
3. Repo → Settings → Secrets and variables → Actions → **Variables** → add
   `SPOTIFY_CLIENT_ID` (or skip and paste the ID into the app's Settings page —
   it persists in localStorage).
4. Optional YouTube: Google Cloud OAuth **Web application** client with the Pages
   origin in Authorized JavaScript origins; set `YOUTUBE_CLIENT_ID` variable.
5. Push to main → Actions builds & deploys.
Local dev: `npm run dev`, open **http://127.0.0.1:5173/** (must be 127.0.0.1 —
Spotify no longer accepts `localhost` redirect URIs).
Note the Spotify app "Development mode" allowlist (add users in the dashboard).
