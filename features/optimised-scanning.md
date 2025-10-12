# Optimize API Calls for Already-Downloaded Songs

## Problem Statement

When downloading playlists where most songs have already been downloaded, Zotify makes unnecessary API calls before checking if the song should be skipped. This significantly slows down the process.

**Current Performance:**
- Downloading a 500-song playlist where 490 songs are already downloaded
- Makes ~1000 API calls (2 per song × 500 songs)
- Only then skips 490 songs after wasting time on metadata fetching

**Target Performance:**
- Skip check BEFORE API calls
- Reduces to ~20 API calls (10 new songs × 2 calls each)
- **50x reduction in API calls** for this use case

## Current Flow Analysis

### Main Iteration Points

**1. Playlist Downloads** (`app.py:107-122`):
```python
for song in playlist_songs:
    if not song[TRACK][NAME] or not song[TRACK][ID]:
        # Skip deleted songs
    else:
        download_track('playlist', song[TRACK][ID], ...)
    enum += 1
```

**2. Liked Songs** (`app.py:56-60`):
```python
for song in get_saved_tracks():
    if not song[TRACK][NAME] or not song[TRACK][ID]:
        # Skip deleted songs
    else:
        download_track('liked', song[TRACK][ID])
```

### The Bottleneck in `download_track()`

**Current execution order** (`track.py:171-324`):

1. **Lines 177-184**: Fetches track metadata for EVERY song via `get_song_info()`
2. **Lines 78-102** in `get_song_info()`: Makes TWO API calls per track:
   - `TRACKS_URL` - Get track info
   - `albums/{album_id}` - Get album info (for album artist placeholders)
3. **Lines 212-214**: Performs skip checks AFTER fetching all metadata:
   ```python
   check_name = Path(filename).is_file() and Path(filename).stat().st_size
   check_id = scraped_song_id in get_directory_song_ids(filedir)
   check_all_time = scraped_song_id in get_previously_downloaded()
   ```
4. **Lines 240-246**: Actually skips the song AFTER wasting API calls

### Additional Inefficiency

**Archive File Re-reading** (`utils.py:35-45`):
```python
def get_previously_downloaded() -> List[str]:
    ids = []
    archive_path = Zotify.CONFIG.get_song_archive()
    if Path(archive_path).exists():
        with open(archive_path, 'r', encoding='utf-8') as f:
            ids = [line.strip().split('\t')[0] for line in f.readlines()]
    return ids
```

- Called once per song in the skip check
- For 500 songs, reads the entire archive file 500 times
- Should load once and reuse

## Proposed Solution

### Option 1: Early Skip Check at Iteration Level (Recommended)

Move skip logic to where we iterate through songs, BEFORE calling `download_track()`.

**Implementation in `app.py`:**

```python
def download_from_urls(urls: list[str]) -> bool:
    # Load archive once at start
    archive_ids = set(get_previously_downloaded()) if Zotify.CONFIG.get_skip_previously_downloaded() else set()

    for spotify_url in urls:
        # ... existing URL parsing ...

        elif playlist_id is not None:
            download = True
            playlist_songs = get_playlist_songs(playlist_id)
            name, _ = get_playlist_info(playlist_id)

            # Pre-load directory song IDs if using skip_existing
            filedir = None
            directory_ids = set()
            if Zotify.CONFIG.get_skip_existing():
                # Calculate filedir once (similar to track.py logic)
                output_template = Zotify.CONFIG.get_output('playlist')
                # ... calculate filedir from output template ...
                directory_ids = set(get_directory_song_ids(filedir))

            enum = 1
            char_num = len(str(len(playlist_songs)))
            for song in playlist_songs:
                if not song[TRACK][NAME] or not song[TRACK][ID]:
                    Printer.print(PrintChannel.SKIPS, '###   SKIPPING:  SONG DOES NOT EXIST ANYMORE   ###' + "\n")
                    continue

                track_id = song[TRACK][ID]

                # Early skip check - NO API CALLS NEEDED
                if Zotify.CONFIG.get_skip_previously_downloaded() and track_id in archive_ids:
                    Printer.print(PrintChannel.SKIPS, f'\n###   SKIPPING: {song[TRACK][NAME]} (SONG ALREADY DOWNLOADED ONCE)   ###\n')
                    enum += 1
                    continue

                # Note: skip_existing check requires filename calculation, so it stays in download_track()

                if song[TRACK][TYPE] == "episode":
                    download_episode(song[TRACK][ID])
                else:
                    download_track('playlist', track_id, extra_keys={...})
                enum += 1
```

**Similar changes needed in:**
- `app.py:56-60` - Liked songs loop
- `playlist.py:52-58` - `download_playlist()` function
- `album.py` - Album download iterations

### Option 2: Lazy Metadata Fetching

Keep the logic in `download_track()` but reorganize to check archive before API calls.

**Challenges:**
- Track ID in archive might differ from scraped track ID (line 249: `if track_id != scraped_song_id`)
- Need filename for file existence check, which requires metadata
- More complex refactoring

### Option 3: Hybrid Approach (Best Performance)

1. **Early archive check** at iteration level (Option 1)
2. **Cache archive in memory** - Load once per session
3. **Keep skip_existing check** in `download_track()` (requires filename)

## Implementation Plan

1. **Add archive caching** (`utils.py`):
   ```python
   _archive_cache = None

   def get_previously_downloaded(use_cache=True) -> set[str]:
       global _archive_cache
       if use_cache and _archive_cache is not None:
           return _archive_cache

       ids = set()
       archive_path = Zotify.CONFIG.get_song_archive()
       if Path(archive_path).exists():
           with open(archive_path, 'r', encoding='utf-8') as f:
               ids = {line.strip().split('\t')[0] for line in f.readlines()}

       if use_cache:
           _archive_cache = ids
       return ids

   def invalidate_archive_cache():
       global _archive_cache
       _archive_cache = None
   ```

2. **Add early skip checks** in iteration loops:
   - `app.py:download_from_urls()` - Playlist downloads
   - `app.py:client()` - Liked songs
   - `playlist.py:download_playlist()`
   - Similar pattern for albums/artists

3. **Update archive writes** to invalidate cache:
   ```python
   def add_to_archive(...):
       # ... existing code ...
       invalidate_archive_cache()
   ```

4. **Keep existing skip logic** in `download_track()` as fallback for:
   - File existence checks (skip_existing)
   - Direct track downloads (not from playlists)

## Expected Performance Improvements

### Example: 500-song playlist, 490 already downloaded

**Current:**
- 500 tracks × 2 API calls = 1000 API calls
- 500 archive file reads
- ~5-10 minutes of wasted API requests

**After optimization:**
- 490 early skips = 0 API calls
- 10 new tracks × 2 API calls = 20 API calls
- 1 archive file read
- **50x reduction in API calls**
- **Seconds instead of minutes for skip checks**

### Example: Re-downloading entire library (10,000 songs)

**Current:**
- 10,000 × 2 = 20,000 API calls
- 10,000 archive file reads
- Hours of unnecessary work

**After optimization:**
- 10,000 early skips = 0 API calls
- 1 archive file read
- **Instant skip confirmation**

## Testing Strategy

1. Create test playlist with mix of downloaded/new songs
2. Measure API calls (add debug logging to `Zotify.invoke_url()`)
3. Verify skip messages appear instantly
4. Confirm new songs still download correctly
5. Test all download modes (playlist, liked, album, artist)

## File References

- `app.py:107-122` - Playlist iteration loop
- `app.py:56-60` - Liked songs loop
- `track.py:171-324` - `download_track()` function
- `track.py:49-105` - `get_song_info()` with API calls
- `track.py:212-214` - Skip checks
- `utils.py:35-45` - Archive file reading
- `playlist.py:52-58` - Playlist download function
