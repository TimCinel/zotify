# Zotify Roadmap

## Completed Improvements

### ✅ Various Artists Metadata Bug (2025-11-17)
**Problem:** Tracks were incorrectly getting album artist "Various Artists" when Spotify API returned album data without ARTISTS field.

**Solution Implemented:**
- Fixed `track.py:78-105` to properly fall back to track artist instead of defaulting to "Various Artists"
- Created `find_broken_various_artists.py` script to identify affected tracks in Plex
- Documented Plex "Fix Match" workflow for correcting existing issues

**Files Modified:**
- `zotify/track.py` - Fixed default initialization bug
- `find_broken_various_artists.py` - Detection script for Plex issues
- `notes/2025-11-17 Troubleshoot Various Artists problems` - Full documentation

---

## Planned Improvements

### Network Failure Handling
**Current behavior:** When album metadata API calls fail, Zotify silently falls back to using the first track artist as the album artist.

**Proposed behavior:**
- Implement proper retry logic with exponential backoff
- After exhausting retries, fail explicitly rather than silent fallback
- Log network failures clearly for debugging
- Consider: Make retry count/delay configurable

**Rationale:** Silent fallbacks can mask real issues and lead to incorrect metadata. Users should know when API calls are failing.

---

### Persist Spotify Track ID in Metadata
**Current behavior:** Track IDs are stored in `.song_ids` files in each album directory, which can be lost if files are moved.

**Proposed implementation:**
- Store Spotify track ID in ID3 `comment` tag (e.g., `"spotify:track:7J8F8mHNV79WSV3N2lVwHH"`)
- Alternatively: Use a custom ID3 frame like `TXXX:SPOTIFY_ID`
- Benefits:
  - Track provenance travels with the file
  - Easy re-download/update tracking
  - No dependency on `.song_ids` files
  - Useful for debugging metadata issues

**Example:**
```python
tags['comment'] = f"spotify:track:{track_id}"
# or
tags['#SPOTIFY_ID'] = track_id  # Custom field
```
