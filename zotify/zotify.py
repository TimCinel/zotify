import json
from pathlib import Path
from pwinput import pwinput
import time
import requests
from librespot.audio.decoders import VorbisOnlyAudioQuality
from librespot.core import Session

from zotify.const import TYPE, \
    PREMIUM, USER_READ_EMAIL, OFFSET, LIMIT, \
    PLAYLIST_READ_PRIVATE, USER_LIBRARY_READ, USER_FOLLOW_READ
from zotify.config import Config

class Zotify:    
    SESSION: Session = None
    DOWNLOAD_QUALITY = None
    CONFIG: Config = Config()

    def __init__(self, args):
        Zotify.CONFIG.load(args)
        Zotify.login(args)

    @classmethod
    def _create_session_with_retry(cls, session_builder, initial_delay=1):
        """ Creates a session with retry logic and exponential backoff for connection errors """
        from zotify.termoutput import Printer, PrintChannel

        max_retries = cls.CONFIG.get_connection_retries()
        for attempt in range(max_retries):
            try:
                return session_builder.create()
            except ConnectionRefusedError as e:
                if attempt < max_retries - 1:
                    delay = initial_delay * (2 ** attempt)  # Exponential backoff
                    Printer.print(PrintChannel.WARNINGS, f"Connection refused (attempt {attempt + 1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    Printer.print(PrintChannel.ERRORS, f"Failed to connect to Spotify after {max_retries} attempts: {e}")
                    raise
            except OSError as e:
                # Catch other connection-related errors (timeout, network unreachable, etc.)
                if attempt < max_retries - 1:
                    delay = initial_delay * (2 ** attempt)
                    Printer.print(PrintChannel.WARNINGS, f"Connection error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    Printer.print(PrintChannel.ERRORS, f"Failed to connect to Spotify after {max_retries} attempts: {e}")
                    raise
            except RuntimeError as e:
                # RuntimeError is for authentication failures, don't retry
                raise

    @classmethod
    def login(cls, args):
        """ Authenticates with Spotify and saves credentials to a file """

        cred_location = Config.get_credentials_location()

        if Path(cred_location).is_file():
            try:
                conf = Session.Configuration.Builder().set_store_credentials(False).build()
                session_builder = Session.Builder(conf).stored_file(cred_location)
                cls.SESSION = cls._create_session_with_retry(session_builder)
                return
            except RuntimeError:
                pass
        while True:
            user_name = args.username if args.username else ''
            while len(user_name) == 0:
                user_name = input('Username: ')
            password = args.password if args.password else pwinput(prompt='Password: ', mask='*')
            try:
                if Config.get_save_credentials():
                    conf = Session.Configuration.Builder().set_stored_credential_file(cred_location).build()
                else:
                    conf = Session.Configuration.Builder().set_store_credentials(False).build()
                session_builder = Session.Builder(conf).user_pass(user_name, password)
                cls.SESSION = cls._create_session_with_retry(session_builder)
                return
            except RuntimeError:
                pass

    @classmethod
    def get_content_stream(cls, content_id, quality):
        return cls.SESSION.content_feeder().load(content_id, VorbisOnlyAudioQuality(quality), False, None)

    @classmethod
    def __get_auth_token(cls):
        return cls.SESSION.tokens().get_token(
            USER_READ_EMAIL, PLAYLIST_READ_PRIVATE, USER_LIBRARY_READ, USER_FOLLOW_READ
        ).access_token

    @classmethod
    def get_auth_header(cls):
        return {
            'Authorization': f'Bearer {cls.__get_auth_token()}',
            'Accept-Language': f'{cls.CONFIG.get_language()}',
            'Accept': 'application/json',
            'app-platform': 'WebPlayer',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        }

    @classmethod
    def get_auth_header_and_params(cls, limit, offset):
        return {
            'Authorization': f'Bearer {cls.__get_auth_token()}',
            'Accept-Language': f'{cls.CONFIG.get_language()}',
            'Accept': 'application/json',
            'app-platform': 'WebPlayer'
        }, {LIMIT: limit, OFFSET: offset}

    @classmethod
    def invoke_url_with_params(cls, url, limit, offset, **kwargs):
        headers, params = cls.get_auth_header_and_params(limit=limit, offset=offset)
        params.update(kwargs)
        return requests.get(url, headers=headers, params=params).json()

    @classmethod
    def invoke_url(cls, url, tryCount=0):
        # we need to import that here, otherwise we will get circular imports!
        from zotify.termoutput import Printer, PrintChannel
        headers = cls.get_auth_header()
        response = requests.get(url, headers=headers)
        responsetext = response.text
        try:
            responsejson = response.json()
        except json.decoder.JSONDecodeError:
            responsejson = {"error": {"status": "unknown", "message": "received an empty response"}}

        if not responsejson or 'error' in responsejson:
            if tryCount < (cls.CONFIG.get_retry_attempts() - 1):
                Printer.print(PrintChannel.WARNINGS, f"Spotify API Error (try {tryCount + 1}) ({responsejson['error']['status']}): {responsejson['error']['message']}")
                time.sleep(5)
                return cls.invoke_url(url, tryCount + 1)

            Printer.print(PrintChannel.API_ERRORS, f"Spotify API Error ({responsejson['error']['status']}): {responsejson['error']['message']}")

        return responsetext, responsejson

    @classmethod
    def check_premium(cls) -> bool:
        """ If user has spotify premium return true """
        return (cls.SESSION.get_user_attribute(TYPE) == PREMIUM)
