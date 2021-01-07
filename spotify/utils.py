import lyricsgenius
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
from os import getenv
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session


load_dotenv()
SCOPE="user-library-read user-top-read"
SPOTIPY_CLIENT_ID=getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET=getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI=getenv("SPOTIPY_REDIRECT_URI")
GENIUS_ACCESS_TOKEN=getenv("GENIUS_ACCESS_TOKEN")


# Checks to see if token is valid and gets a new token if not
def get_token(session):
    """Checks to see if there's a valid token for the current session and/or 
        whether an existing token is expired. 
        If expired, it grabs the refresh token."""

    token_valid = False
    token_info = session.get("token_info", {})

    # Checking if the session already has a token stored
    if not (session.get('token_info', False)):
        token_valid = False
        return token_info, token_valid

    # Checking if token has expired
    now = int(time.time())
    is_token_expired = session.get('token_info').get('expires_at') - now < 60

    # Refreshing token if it has expired
    if (is_token_expired):
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(
            session.get('token_info').get('refresh_token')
        )

    token_valid = True
    return token_info, token_valid


def get_sp(session):
    """
    Creates spotify object to make API call. If the user has not yet 
    authorized in the current session, they are directed back to the home 
    page. If they have already authorized, a Spotify object with an access 
    token is created, which is then used to make the appropriate API call.
    """

    session["token_info"], authorized=get_token(session)
    if not authorized:
        return redirect("/")
    return spotipy.Spotify(auth=session.get('token_info').get('access_token'), 
                                            requests_timeout=10)


def create_spotify_oauth():
    """Helper function to create SpotifyOAuth object"""
  
    return SpotifyOAuth(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            redirect_uri=SPOTIPY_REDIRECT_URI,            
            scope=SCOPE)


def get_lyrics(artist_names, track_names):
    """
    this docstring is epic - Trey
    Input:  artist_names - A list of artist names
            track_names - A list of track names

    Returns: A list of lyrics corresponding to each track 
    """
    genius=lyricsgenius.Genius(GENIUS_ACCESS_TOKEN)

    lyrics=[]
    for idx, track in enumerate(track_names):
        artist = genius.search_artist(artist_names[idx], max_songs=0)
        lyrics.append(artist.song(track).lyrics)
    return lyrics



if __name__ == "__main__":
    print('DEBUG MODE DETECTED FOR UTILS.PY - TESTING WITH DUMMY DATA')
    genius=lyricsgenius.Genius(GENIUS_ACCESS_TOKEN)
    artist = genius.search_artist("Britney Spears", max_songs=0)
    song=artist.song("Toxic")
    print(song.lyrics)
           
