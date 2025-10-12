from zotify.const import ITEMS, ARTISTS, NAME, ID
from zotify.termoutput import Printer, PrintChannel
from zotify.track import download_track
from zotify.utils import fix_filename, get_previously_downloaded
from zotify.zotify import Zotify

ALBUM_URL = 'https://api.spotify.com/v1/albums'
ARTIST_URL = 'https://api.spotify.com/v1/artists'


def get_album_tracks(album_id):
    """ Returns album tracklist """
    songs = []
    offset = 0
    limit = 50

    while True:
        resp = Zotify.invoke_url_with_params(f'{ALBUM_URL}/{album_id}/tracks', limit=limit, offset=offset)
        offset += limit
        songs.extend(resp[ITEMS])
        if len(resp[ITEMS]) < limit:
            break

    return songs


def get_album_name(album_id):
    """ Returns album name """
    (raw, resp) = Zotify.invoke_url(f'{ALBUM_URL}/{album_id}')
    return resp[ARTISTS][0][NAME], fix_filename(resp[NAME])


def get_artist_albums(artist_id):
    """ Returns artist's albums """
    (raw, resp) = Zotify.invoke_url(f'{ARTIST_URL}/{artist_id}/albums?include_groups=album%2Csingle')
    # Return a list each album's id
    album_ids = [resp[ITEMS][i][ID] for i in range(len(resp[ITEMS]))]
    # Recursive requests to get all albums including singles an EPs
    while resp['next'] is not None:
        (raw, resp) = Zotify.invoke_url(resp['next'])
        album_ids.extend([resp[ITEMS][i][ID] for i in range(len(resp[ITEMS]))])

    return album_ids


def download_album(album):
    """ Downloads songs from an album """
    # Load archive once at start for early skip checks
    archive_ids = get_previously_downloaded() if Zotify.CONFIG.get_skip_previously_downloaded() else set()

    artist, album_name = get_album_name(album)
    tracks = get_album_tracks(album)
    for n, track in Printer.progress(enumerate(tracks, start=1), unit_scale=True, unit='Song', total=len(tracks)):
        track_id = track[ID]

        # Early skip check - avoid API calls for already downloaded songs
        if Zotify.CONFIG.get_skip_previously_downloaded() and track_id in archive_ids:
            Printer.print(PrintChannel.SKIPS, f'Skipping track {track_id} (already downloaded)')
            continue

        download_track('album', track_id, extra_keys={'album_num': str(n).zfill(2), 'artist': artist, 'album': album_name, 'album_id': album}, disable_progressbar=True)


def download_artist_albums(artist):
    """ Downloads albums of an artist """
    albums = get_artist_albums(artist)
    for album_id in albums:
        download_album(album_id)
