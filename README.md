# NTS Radio to Spotify Playlist Automation

A Python-based tool for extracting track listings from [NTS Radio](https://www.nts.live/) episodes and creating corresponding Spotify playlists. This project automates the process of capturing DJ-curated music from NTS shows and adding them to your Spotify library.

## Overview

NTS Radio hosts an incredible collection of DJ mixes and radio shows, but there's no built-in way to save the tracklists to Spotify. This tool bridges that gap by:

1. **Discovering** all episodes from a specific NTS Radio show
2. **Extracting** track listings from episode pages
3. **Cleaning** and normalizing the track/artist data
4. **Creating** Spotify playlists with the extracted tracks (in development)

## Features

- 🎵 Scrape track listings from individual or multiple NTS Radio episodes
- 📅 Organize episodes by year for batch processing
- 🧹 Clean and normalize track/artist names (removes accents, "feat." annotations, etc.)
- 📊 Export tracklists to CSV format
- 🔄 Track which episodes have been processed
- ✨ **Enrich tracks with 29+ metadata fields from Spotify, Last.fm, and MusicBrainz**
- 🎧 Spotify playlist creation (partially implemented)

## Project Structure

```
nts_to_spotify/
├── nts_show_to_csv.py            # ⭐ Main script - show name to CSV in one command
├── enrich_tracks.py              # ⭐ Enrich CSV with Spotify/Last.fm/MusicBrainz data
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variable template
│
├── scripts/                      # Individual NTS scraping scripts
│   ├── nts_get_track_list.py    # Extract tracks from a single episode
│   ├── cli_get_tracks.py        # Batch process episodes (CLI)
│   ├── multi_get_tracklist.py   # Batch process episodes (interactive)
│   ├── pull_dj_links.py         # Discover all episodes from a DJ's show
│   ├── other_curl.py            # Alternative episode discovery tool
│   ├── sort_urls.py             # Organize episode URLs by year
│   ├── reset_urls.sh            # Archive processed URLs and CSVs
│   ├── episodes.txt             # Master list of episode URLs
│   ├── read_urls.txt            # Processed episode URLs
│   └── by_year/                 # Episode URLs organized by year
│
├── spotify_scripts/              # Spotify API integration
│   ├── spotify_nts_playlist.py  # Spotify playlist creation (v1)
│   └── spotify_v2.py            # Improved Spotify integration (v2)
│
├── unread_csvs/                  # CSVs not yet uploaded to Spotify
├── read_csvss/                   # CSVs already uploaded to Spotify
└── datasets/                     # Archive of collected data
```

## Prerequisites

- Python 3.x
- A Spotify Developer account (for playlist creation)

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd nts_to_spotify
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required dependencies:
```bash
pip install -r requirements.txt
```

Required packages (defined in requirements.txt):
- `requests` - HTTP requests to NTS and Spotify APIs
- `beautifulsoup4` - HTML parsing
- `unidecode` - Text normalization (removes accents)
- `python-dotenv` - Environment variable management
- `pandas` - Data analysis (optional)

4. Set up environment variables for Spotify:
```bash
cp .env.example .env
```

Edit `.env` and add your Spotify API credentials:
```bash
SPOTIFY_CLIENT_ID=your_actual_client_id
SPOTIFY_CLIENT_SECRET=your_actual_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8000/callback/
```

To get Spotify credentials:
- Go to https://developer.spotify.com/dashboard
- Create a new app
- Copy your Client ID and Client Secret
- Add `http://localhost:8000/callback/` as a Redirect URI in your app settings

## Usage

### Quick Start (Recommended)

The easiest way to extract all tracks from an NTS show is using the all-in-one script:

```bash
python nts_show_to_csv.py <show_name>
```

Example:
```bash
# Extract all tracks from Rachel Grace Almeida's show
python nts_show_to_csv.py rachel-grace-almeida

# Specify a custom output filename
python nts_show_to_csv.py miss-modular miss_modular_complete.csv
```

This single command will:
1. 🔍 Discover all episodes from the show
2. 📥 Extract tracks from every episode
3. 💾 Save everything to a CSV file

The script shows progress in real-time and creates:
- `<show_name>_complete.csv` - All tracks with episode URLs
- `nts_show_to_csv.log` - Detailed log file

**Finding the show name:**
- Go to the show page on NTS (e.g., `https://www.nts.live/shows/rachel-grace-almeida`)
- The show name is the last part of the URL: `rachel-grace-almeida`

### Data Enrichment (Add Metadata to Your Tracks)

Once you have a CSV of tracks, enrich it with detailed metadata from multiple sources:

```bash
python enrich_tracks.py <input_csv>
```

Example:
```bash
# Enrich the complete tracklist
python enrich_tracks.py rachel-grace-almeida_complete.csv

# Specify custom output filename
python enrich_tracks.py tracks.csv enriched_output.csv
```

**What you get:**

**From Spotify (19 fields):**
- Audio features: danceability, energy, tempo, valence, acousticness, instrumentalness, liveness, speechiness
- Musical properties: key, mode, time signature, loudness
- Metadata: popularity, duration, album, release date, preview URL, explicit flag

**From Last.fm (4 fields):**
- Play count across all Last.fm users
- Total listener count
- Community tags/genres
- Last.fm track URL

**From MusicBrainz (6 fields):**
- Recording ID and metadata
- Release date and country
- Community tags
- Track length

**Example output:**
```
============================================================
Data Sources:
  Spotify ✓
  Last.fm ✓
  MusicBrainz ✓

Processing 892 tracks...

✓ Enrichment complete

Match rates:
  Spotify: 847/892 (95.0%)
  Last.fm: 723/892 (81.1%)
  MusicBrainz: 654/892 (73.3%)

Output file: rachel-grace-almeida_complete_enriched.csv
============================================================
```

**Setup for enrichment:**
1. Spotify credentials are required (already set up in `.env`)
2. Last.fm API key is optional but recommended:
   - Create account at https://www.last.fm
   - Get API key at https://www.last.fm/api/account/create
   - Add to `.env`: `LASTFM_API_KEY=your_key_here`
3. MusicBrainz requires no setup (free, no key needed)

The script handles rate limiting automatically and shows real-time progress!

### Advanced Usage (Individual Scripts)

If you need more control over the process, you can use the individual scripts:

#### Step 1: Discover Episodes from a DJ's Show

Use `pull_dj_links.py` to scrape all episode URLs from a specific NTS show:

```bash
cd scripts
python pull_dj_links.py
```

When prompted, enter the show name (e.g., `rachel-grace-almeida`, `miss-modular`). The script will:
- Call the NTS API to retrieve all episodes
- Organize episodes by year in `by_year/` directory
- Save all URLs to `episodes.txt`
- Suggest next commands to run

### Step 2: Extract Track Listings

#### Option A: Single Episode

```bash
python nts_get_track_list.py
```

You'll be prompted for:
- Episode URL (e.g., `https://www.nts.live/shows/guest/episodes/episode-123`)
- CSV title (filename for the output)

#### Option B: Batch Processing (Recommended)

Using the CLI version:
```bash
python cli_get_tracks.py <url_file> <csv_title>
```

Example:
```bash
python cli_get_tracks.py by_year/2023.txt rachel_2023
```

Using the interactive version:
```bash
python multi_get_tracklist.py
```

The scripts will:
- Parse each episode page using BeautifulSoup
- Extract track titles and artists from the `#episode-container` element
- Clean the data (lowercase, remove accents, strip "feat." annotations)
- Save to `../unread_csvs/<csv_title>.csv`

### Step 3: Organize URLs by Year

If you have a large list of URLs in `episodes.txt`, organize them by year:

```bash
python sort_urls.py
```

This creates separate files in `by_year/` for easier batch processing.

### Step 4: Create Spotify Playlists

⚠️ **Note:** The Spotify integration is currently incomplete but functional through the authorization flow.

1. Ensure you've set up your `.env` file with Spotify credentials (see Installation step 4)

2. Run the script:
```bash
cd spotify_scripts
python spotify_v2.py
```

The script will:
- Open your browser for Spotify authorization
- Create a new playlist
- Search for tracks from your CSV (needs to be integrated)
- Add found tracks to the playlist

### Step 5: Archive Processed Data

After uploading tracks to Spotify, run the maintenance script:

```bash
cd scripts
./reset_urls.sh
```

This will:
- Move processed URLs to `read_urls.txt`
- Move uploaded CSVs from `unread_csvs/` to `read_csvss/`
- Clear the working `urls.txt` file

## How It Works

### Web Scraping

The tool uses BeautifulSoup to parse NTS Radio episode pages. Each episode page contains a container with ID `episode-container` that holds individual track elements with class `track`. Each track has:
- `track__title` - The song title
- `track__artist` - The artist name

### Data Cleaning

The `clean_string()` function in scripts/cli_get_tracks.py:19-19 normalizes text by:
- Converting Unicode characters to ASCII (e.g., "café" → "cafe")
- Converting to lowercase
- Removing extra whitespace
- Stripping "ft" and "feat" annotations (e.g., "Song ft. Artist" → "Song")

### CSV Output Format

The consolidated script (`nts_show_to_csv.py`) outputs:

```csv
TITLE,ARTIST,EPISODE_URL
song title,artist name,https://www.nts.live/shows/show-name/episodes/episode-1
another song,another artist,https://www.nts.live/shows/show-name/episodes/episode-1
```

The enrichment script (`enrich_tracks.py`) adds 29 additional columns:

**Spotify Fields (19):**
- `spotify_id`, `spotify_popularity`, `spotify_duration_ms`, `spotify_explicit`
- `spotify_preview_url`, `spotify_album`, `spotify_release_date`
- `spotify_danceability`, `spotify_energy`, `spotify_key`, `spotify_loudness`
- `spotify_mode`, `spotify_speechiness`, `spotify_acousticness`
- `spotify_instrumentalness`, `spotify_liveness`, `spotify_valence`
- `spotify_tempo`, `spotify_time_signature`

**Last.fm Fields (4):**
- `lastfm_playcount`, `lastfm_listeners`, `lastfm_tags`, `lastfm_url`

**MusicBrainz Fields (6):**
- `musicbrainz_id`, `musicbrainz_title`, `musicbrainz_length`
- `musicbrainz_tags`, `musicbrainz_country`, `musicbrainz_date`

The individual scripts output:

```csv
TITLE,ARTIST
song title,artist name
another song,another artist
```

## Workflow Examples

### Simple Workflow (Recommended)

Extract and enrich tracks from a show:

```bash
# Step 1: Get complete tracklist for a show
python nts_show_to_csv.py rachel-grace-almeida
# Output: rachel-grace-almeida_complete.csv with all tracks

# Step 2: Enrich with metadata from Spotify, Last.fm, and MusicBrainz
python enrich_tracks.py rachel-grace-almeida_complete.csv
# Output: rachel-grace-almeida_complete_enriched.csv with 29+ additional data fields
```

**Complete pipeline in 2 commands** - from show name to fully enriched dataset!

### Advanced Workflow

Complete workflow for archiving a DJ's catalog with more control:

```bash
# 1. Discover all episodes from a show
cd scripts
python pull_dj_links.py
# Enter show name: rachel-grace-almeida

# 2. Process 2023 episodes
python cli_get_tracks.py by_year/2023.txt rachel_2023

# 3. Process 2022 episodes
python cli_get_tracks.py by_year/2022.txt rachel_2022

# 4. Check the generated CSVs
ls ../unread_csvs/

# 5. Upload to Spotify (in development)
cd ../spotify_scripts
python spotify_v2.py

# 6. Archive processed data
cd ../scripts
./reset_urls.sh
```

## Logging

The consolidated script (`nts_show_to_csv.py`) logs to both console and `nts_show_to_csv.log` including:
- Episode discovery progress
- Track extraction status
- HTTP errors and warnings
- Final statistics

The individual track extraction scripts log to `get_tracklist_logs.txt` including:
- HTTP request status codes
- Extracted track and artist names
- Any errors encountered

Check these log files if you encounter issues.

## Current Status

### Completed ✅
- Web scraping from NTS Radio episode pages
- Batch processing of multiple episodes
- Episode discovery and organization by year
- Text cleaning and normalization
- CSV export functionality
- URL tracking system (processed vs. unprocessed)
- Environment variable configuration with `.env` file
- Dependency management with `requirements.txt`
- **Data enrichment with Spotify, Last.fm, and MusicBrainz**
- **Rate limiting and API token caching**

### In Development 🚧
- **Spotify Playlist Creation**: The authorization flow works, but automatic playlist population from CSV needs to be connected
- **Error Handling**: Limited retry logic for failed API requests

### Future Enhancements 💡
- Automatic CSV-to-Spotify playlist pipeline
- Support for other radio stations (Rinse FM, Red Light Radio, etc.)
- Playlist cover art from episode artwork
- Deduplication across multiple episodes
- Data visualization dashboard (show statistics, genre distributions, audio features)
- Track recommendation engine based on enriched audio features

## Troubleshooting

### "No tracks found" error
- Verify the NTS episode page has a tracklist (some episodes don't)
- Check `get_tracklist_logs.txt` for HTTP errors
- Ensure the episode URL is correct and accessible

### Spotify authorization fails
- Verify your Redirect URI matches exactly: `http://localhost:8000/callback/`
- Check that your Client ID and Secret are correct
- Ensure your Spotify app has the `playlist-modify-public` scope enabled

### Dependencies not found
Make sure you've installed all required packages:
```bash
pip install -r requirements.txt
```

### Enrichment script shows low match rates
- **Spotify**: Requires valid credentials in `.env` file
- **Last.fm**: Check that API key is set in `.env` (optional but improves matches)
- **MusicBrainz**: No setup needed, but has strict 1 req/sec rate limit (script handles this automatically)
- Some tracks may not be found due to:
  - Misspellings in original NTS data
  - Tracks not available on that platform
  - Regional availability restrictions
  - Very obscure or underground releases

## Contributing

This is a personal project, but suggestions and improvements are welcome! Areas that need work:
- Completing the Spotify integration (connecting CSV data to playlist creation)
- Adding tests
- Better error handling and retry logic
- Rate limiting for API requests
- Progress bars for batch processing

## License

This project is for personal use. Please respect NTS Radio's terms of service and don't abuse their servers with excessive requests.

## Acknowledgments

- [NTS Radio](https://www.nts.live/) for providing incredible radio content
- [Spotify Web API](https://developer.spotify.com/documentation/web-api/) for playlist management

---

**Note:** This tool is not affiliated with NTS Radio or Spotify. Use responsibly and respect rate limits.
