# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup

This project uses pyenv for Python environment management:

```bash
# Activate the environment
pyenv activate zotify

# Run the application
python -m zotify [arguments]
```

## Core Architecture

Zotify is a Spotify downloader built around several key modules:

- **Authentication & API** (`zotify.py`): Handles Spotify authentication via librespot and API communication
- **Main Application** (`app.py`): Orchestrates downloads and manages the download queue
- **Content Modules**: 
  - `track.py` - Individual song downloads with metadata and lyrics
  - `album.py` - Album and artist catalog downloads
  - `playlist.py` - Playlist management and bulk downloads
  - `podcast.py` - Podcast episode downloads with URL fallbacks
- **Configuration** (`config.py`): Centralized settings management with JSON persistence
- **Utilities** (`utils.py`): File operations, metadata tagging, filename sanitization

## Key Dependencies

- `librespot-python`: Core Spotify streaming and authentication
- `ffmpy`: Audio format conversion via FFmpeg
- `music_tag`: Audio metadata embedding
- `tqdm`: Progress bar displays
- `tabulate`: Search results formatting

## Common Development Patterns

The codebase uses several consistent patterns:
- Config values accessed via `ZCONFIG.get(key, fallback)`
- Progress tracking with `tqdm` for all downloads
- Error handling with graceful fallbacks (especially in podcast downloads)
- Filename sanitization for cross-platform compatibility
- Real-time mode for rate limiting to appear more legitimate

## Common Commands

```bash
# Download from URL
python -m zotify <spotify_url>

# Search and download
python -m zotify -s "artist song name"

# Download liked songs
python -m zotify -l

# Download from file of URLs
python -m zotify -d urls.txt

# Download followed artists
python -m zotify -f

# Download saved playlists
python -m zotify -p
```

## Testing Commands

```bash
# Test basic functionality
python -m zotify -s "test song"

# Test different content types
python -m zotify <spotify_track_url>
python -m zotify <spotify_album_url>
python -m zotify <spotify_playlist_url>
```

## Configuration

- Default config path: `~/Library/Application Support/Zotify/config.json` (macOS)
- Output directory: `~/Music/Zotify Music/`
- Archive file: `song_archive` (tracks already downloaded)

## Known Issues & Development Requirements

### Album Artist Placeholders ✅ IMPLEMENTED

**New Placeholders Available**:
- **`{album_artist}`** - Uses Spotify's album artist exactly as provided
- **`{album_artist_or_various}`** - Uses "Various Artists" for multi-artist albums, otherwise uses album artist

**Enhanced Features**:
- Album metadata fetching integrated into track download process
- **ALBUMARTIST ID3 tag automatically set to "Various Artists"** for multi-artist albums (optimal for Plex/Jellyfin/Subsonic)
- Intelligent "Various Artists" detection (>50% different artists + >3 unique artists)
- Preserves actual album artist information in `{album_artist}` placeholder

**Usage Examples**:
```bash
# Use album artist for organization (preserves Disney, Lin-Manuel Miranda, etc.)
--output "{album_artist}/{album}/{track_number:02d} - {artist} - {song_name}.{ext}"

# Use "Various Artists" for better media server compatibility  
--output "{album_artist_or_various}/{album}/{track_number:02d} - {artist} - {song_name}.{ext}"
```

**Test Results**: 
- Moana soundtrack: `{album_artist}` = "Lin-Manuel Miranda", `{album_artist_or_various}` = "Lin-Manuel Miranda"
- Disney Christmas: `{album_artist}` = "Disney", `{album_artist_or_various}` = "Disney"  
- Lion King: `{album_artist}` = "Various Artists", `{album_artist_or_various}` = "Various Artists"

## Implementation Details

### Files Modified

**`track.py` (Lines 49-105)**:
- Enhanced `get_song_info()` function to fetch album metadata from Spotify API
- Added album artist detection and "Various Artists" logic
- Returns two new values: `album_artist` and `album_artist_or_various`

**`track.py` (Lines 183-203)**:
- Added placeholder replacements for `{album_artist}` and `{album_artist_or_various}`
- Updated function call to pass album artist data to metadata tagging

**`utils.py` (Lines 129-147)**:
- Modified `set_audio_tags()` to accept both album artist parameters
- **ALBUMARTIST ID3 tag priority**: Uses `album_artist_or_various` > `album_artist` > `artists[0]`
- Ensures "Various Artists" is properly set in metadata for multi-artist albums

### Algorithm Logic

**Various Artists Detection**:
```python
# Fetch all tracks in album
album_tracks = album_info.get('tracks', {}).get('items', [])
unique_artists = set()
for track in album_tracks:
    for track_artist in track.get('artists', []):
        unique_artists.add(track_artist['name'])

# If album has >50% tracks with different artists AND >3 unique artists
if len(unique_artists) > len(album_tracks) * 0.5 and len(unique_artists) > 3:
    album_artist_or_various = "Various Artists"
else:
    album_artist_or_various = album_artist
```

### ID3 Tagging Behavior

**For Various Artists Albums (e.g., Lion King)**:
- **ALBUMARTIST** ID3 tag = `"Various Artists"`
- **ARTIST** ID3 tag = `"Carmen Twillie"` (individual track artist)
- **File path** = `Various Artists/The Lion King/01 - Carmen Twillie - Circle of Life.ogg`

**For Single Artist Albums (e.g., Moana)**:
- **ALBUMARTIST** ID3 tag = `"Lin-Manuel Miranda"`
- **ARTIST** ID3 tag = `"Olivia Foa'i"` (individual track artist)  
- **File path** = `Lin-Manuel Miranda/Moana/01 - Olivia Foa'i - Tulou Tagaloa.ogg`

**For Label Compilations (e.g., Disney Christmas)**:
- **ALBUMARTIST** ID3 tag = `"Disney"`
- **ARTIST** ID3 tag = `"Kristen Bell"` (individual track artist)
- **File path** = `Disney/Disney Christmas/01 - Kristen Bell - Do You Want to Build a Snowman.ogg`

### Media Server Compatibility

This implementation provides optimal compatibility with:
- **Plex Media Server**: Recognizes "Various Artists" ALBUMARTIST tags
- **Jellyfin**: Properly groups compilation albums
- **Subsonic/Airsonic**: Standard various artists handling
- **iTunes/Music.app**: Follows Apple's album artist conventions
- **MusicBrainz Picard**: Compatible with standard tagging practices