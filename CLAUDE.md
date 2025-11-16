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

## AAC/SpAC Format Limitation ⚠️ PARTIALLY FIXED (November 2025)

### Problem
Some tracks are only available in AAC format (no VORBIS/MP3). Spotify's AAC uses a proprietary "SpAC" container that cannot be decoded by standard tools:
- ffmpeg: Cannot read SpAC format
- librespot-python: No SpAC decoder
- librespot-rust: Uses Symphonia decoder (supports SpAC)

This causes downloads to fail with "Invalid data found when processing input" errors.

### Solution Implemented

**Modified librespot-python** (`~/src/librespot-python`):
1. **Fallback Logic** (audio/decoders.py:110-157): `VorbisOnlyAudioQuality` now tries VORBIS → MP3 → AAC
2. **Header Handling** (audio/__init__.py:347-352): Only skip 0xa7 bytes for VORBIS format, not AAC/MP3

**Modified zotify** (`zotify/const.py:102-104`):
- Changed OGG/VORBIS codec from `'copy'` to `'libvorbis'` to support transcoding from different source formats

### Current Status
- ✅ Tracks with VORBIS or MP3: Work correctly
- ⚠️ AAC-only tracks: Download succeeds but ffmpeg conversion fails due to SpAC format

### Long-term Fix Needed
To fully support AAC-only tracks, need to either:
1. Port Symphonia's SpAC decoder to Python
2. Create Python bindings for Symphonia
3. Use external decoder tool for AAC streams
4. Skip AAC-only tracks with informative error

### Test Case
Track "5cY8y2XgOfkAh4kSWLFKkz" (Panic! At The Disco - I Write Sins Not Tragedies) only has AAC format available.

## Extended Metadata Endpoint Fix ✅ FIXED (November 2025)

### Problem
In November 2025, Spotify changed their metadata API, causing downloads to fail with "Cannot get alternative track" errors. The old `/metadata/4/track/{id}` endpoint began returning empty file arrays, breaking all downloads.

### Root Cause
1. **API Change**: Spotify migrated to a new `/extended-metadata/v0/extended-metadata` endpoint
2. **Authentication Issue**: The new endpoint requires proper OAuth scopes that stored credentials don't have
3. **Critical Bug**: librespot-python's `PreparedRequest` used `.data` instead of `.body`, causing requests to send with empty bodies

### Solution Implemented

**Modified Dependency**: Uses custom fork of librespot-python at `timcinel/librespot-python:main`

**Key Changes in librespot-python**:

1. **Extended Metadata Support** (`core.py:260-330`):
   - Implemented new `/extended-metadata/v0/extended-metadata` endpoint
   - Added protobuf message definitions (BatchedEntityRequest, EntityRequest, ExtensionQuery)
   - Mirrors fix from [librespot-org/librespot PR #1622](https://github.com/librespot-org/librespot/pull/1622)

2. **Critical Bug Fix** (`core.py:146`):
   ```python
   # BEFORE (broken):
   request.data = body

   # AFTER (fixed):
   request.body = body  # PreparedRequest requires .body not .data
   ```

3. **Authentication Fallback** (`core.py:151-177`):
   - Attempts to use OAuth token from credentials.json when available
   - Falls back to login5/playlist-read tokens for standard stored credentials
   - Ensures both auth methods work with extended metadata endpoint

**Files Added**:
- `librespot/proto/extended_metadata_pb2.py` - Extended metadata message definitions
- `librespot/proto/extension_kind_pb2.py` - Extension type enum (TRACK_V4 = 10)
- `librespot/proto/entity_extension_data_pb2.py` - Entity extension data structures

### Installation

Updated `requirements.txt` to use the fixed fork:
```
https://github.com/timcinel/librespot-python/archive/refs/heads/main.zip
```

### Testing

Verified working with both authentication methods:
- ✅ Stored credentials (long-lasting, months duration)
- ✅ OAuth tokens (short-lived, 1 hour duration)

Test tracks that were previously failing:
- "Lukas Graham - 7 Years" (ID: 5kqIPrATaCc2LqxVWzQGbk)
- "Twenty One Pilots - Stressed Out" (ID: 3CRDbSIZ4r5MsZ0YwxuEkn)

### Technical Details

**Protobuf Request Format**:
```python
entity_request = EntityRequest()
entity_request.entity_uri = "spotify:track:{track_id}"
extension_query = ExtensionQuery()
extension_query.extension_kind = ExtensionKind.TRACK_V4
entity_request.query.append(extension_query)

batched_request = BatchedEntityRequest()
batched_request.entity_request.append(entity_request)
```

**Authentication Priority**:
1. OAuth token from credentials.json (if type = AUTHENTICATION_SPOTIFY_TOKEN)
2. Login5 token with "user-read-email" scope
3. Fallback to "playlist-read" token (legacy compatibility)

### Why All Changes Were Necessary

1. **Protobuf files**: Required to communicate with Spotify's new API structure
2. **Extended metadata endpoint**: Old endpoint no longer returns file URLs
3. **`request.body` fix**: Critical - without this, all requests fail with empty bodies (400/401 errors)
4. **OAuth/login5 fallback**: Stored credentials alone lack sufficient API scopes for extended metadata

### Debugging Notes

Common issues encountered:
- **401 "missing_token"**: Authorization header not set (auth fallback issue)
- **400 Bad Request**: Empty request body (`.data` vs `.body` bug)
- **Token expiration**: OAuth tokens expire in ~1 hour (use stored credentials for long-term use)