""" Primary backend functionalities """

# Built-in
import time
import random
from os import getenv

# Third-party
import lyricsgenius
import ast
import spacy
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
from flask import Flask, render_template, request, redirect, session
from sklearn.preprocessing import MinMaxScaler
from sklearn.neighbors import NearestNeighbors
from dotenv import load_dotenv


load_dotenv()
SCOPE="user-library-read user-top-read"
FEATURE_NAMES=["danceability", "energy", "key", "loudness", "mode", 
               "speechiness", "acousticness", "instrumentalness", "liveness", 
               "valence", "tempo", "duration_ms"]
SPOTIPY_CLIENT_ID=getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET=getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI=getenv("SPOTIPY_REDIRECT_URI")
GENIUS_ACCESS_TOKEN=getenv("GENIUS_ACCESS_TOKEN")

nlp = spacy.load("en_core_web_sm")

# Checks to see if token is valid and gets a new token if not
def get_token(session):
    """
    Checks to see if there's a valid token for the current session and/or 
    whether an existing token is expired. 
    If expired, it grabs the refresh token.
    """

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
    """Helper function to create SpotifyOAuth object."""
  
    return SpotifyOAuth(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            redirect_uri=SPOTIPY_REDIRECT_URI,            
            scope=SCOPE)


def get_lyrics(artists, songs):
    """
    Input:  artists - A list of artist names
            songs - A list of track names

    Returns: A list of lyrics corresponding to each track 
    """
    genius = lyricsgenius.Genius(GENIUS_ACCESS_TOKEN)
    lyrics = []
    for song, artist in zip(songs, artists):
        lyric = genius.search_song(song, artist)
        if lyric:
            lyrics.append(lyric.lyrics)
        if len(lyrics) > 0:
            break
    return lyrics


def normalize_data(df):
    """Normalizes a dataframe."""

    scaler=MinMaxScaler()
    df[FEATURE_NAMES] = scaler.fit_transform(df[FEATURE_NAMES])
    return df


def recommend(features_df, data_df, bad=True):
    """
    Input: features_df - a dataframe of audio features for the user's top tracks
            data_df - the song dataset

    Returns: List of names of the 10 songs that is most dissimilar to the 
             average of the user's audio features as determined by 
             NearestNeighbors.
    """

    features_df=normalize_data(features_df).values
    data_df = normalize_data(data_df)

    # Take average of features_df to form the user's average profile
    user_avg = features_df.mean(axis=0).reshape(1,-1)

    # Get data_df features with which to find nearest neighbors of user_avg
    samples = data_df[FEATURE_NAMES].values

    neigh=NearestNeighbors(n_neighbors=len(data_df))
    neigh.fit(samples)

    # Order songs by similarity to users top songs.
    ordered = neigh.kneighbors(user_avg, return_distance=False).flatten()

    # Good/bad recommendation split.
    if bad:
        print('generated bad')
        # Generate and pull random low indexes from ordered list.
        random_indexes = []
        while len(random_indexes) < 10:
            index = random.randrange(-300, 0)
            if index not in random_indexes:
                random_indexes.append(index)
        recommendations = [ordered[index] for index in random_indexes]

        # Return song names of recommendations
        rec_names = [data_df.iloc[rec]["name"] for rec in recommendations]

        # Return song ids of recommendations 
        rec_ids = [data_df.iloc[rec]["id"] for rec in recommendations]
    else:
        print('generated good')
        # Generate and pull random high indexes from ordered list.
        random_indexes = []
        while len(random_indexes) < 10:
            index = random.randrange(0, 100)
            if index not in random_indexes:
                random_indexes.append(index)
        recommendations = [ordered[index] for index in random_indexes]

        rec_names = [data_df.iloc[rec]["name"] for rec in recommendations]

        rec_ids = [data_df.iloc[rec]["id"] for rec in recommendations]

    # Return artists of each song in recommendations (used for getting lyrics). 
    # If multiple artists on each track, choose the first one. 
    rec_artists = [ast.literal_eval(data_df.iloc[rec]["artists"])[0] 
                   for rec in recommendations]

    return rec_names, rec_ids, rec_artists


def song_links(ids):
    """
    Takes a list of Spotify track ids and returns a list of the corresponding 
    track uris on Spotify
    """
    sp = get_sp(session)
    all_tracks = sp.tracks(ids)
    links = [song['uri'] for song in all_tracks["tracks"]]
    return links


def generate_noun_chunks(lyrics_list):
    lyrics_list = [lyric.replace("\n", " ").strip() for lyric in lyrics_list]
    all_chunks = []
    for doc in nlp.pipe(lyrics_list):
        doc_chunks = [noun.text for noun in doc.noun_chunks]
        all_chunks.append(doc_chunks)
    all_chunks = [noun for each_doc in all_chunks for noun in each_doc]
    return all_chunks


def choose_name(noun_chunks):
    """
    Takes a list of lyrics and chooses a phrase at random to set as an amusing 
    playlist name. The selected phrases are extracted with the spaCy library's 
    noun chunks.
    """
    word_length = 0
    conjs = ["and", "or", "but"]
    while word_length < 3:
        playlist = random.choice(noun_chunks)
        word_length = len(playlist.split())
    if word_length > 4:
        p_list = random.sample(playlist.split(), k=2)
        play_name = " ".join(p_list)
        while play_name.lower().startswith(tuple(conjs)) or play_name.lower().endswith(tuple(conjs)):
          p_list = random.sample(playlist.split(), k=2)
          play_name = " ".join(p_list)
        return play_name.title()
    else:
        return playlist.title()
    

if __name__ == "__main__":
    print('DEBUG MODE DETECTED FOR UTILS.PY - TESTING WITH DUMMY DATA')
    genius=lyricsgenius.Genius(GENIUS_ACCESS_TOKEN)
    # artist = genius.search_artist("Britney Spears", max_songs=0)
    # song=artist.song("Toxic")
    # print(song.lyrics)

    def get_lyrics(artists, songs):
        """
        Input:  artists - A list of artist names
                songs - A list of track names

        Returns: A list of lyrics corresponding to each track 
        """
        genius=lyricsgenius.Genius(GENIUS_ACCESS_TOKEN)

        lyrics = []
        for song, artist in zip(song, artists):
            lyric = genius.search_song(song, artist)
            if lyric:
                print('APPENDED')
                lyrics.append(lyric)
            if len(lyrics) > 1:
                print('BROKE')
                break

        return lyrics

    ARTISTS = ["Lana Del Rey", "Bahamas", "Five Finger Death Punch", "Green Day"]
    SONGS = ["Salvatore", "No Depression", "Wrong Side of Heaven", "Boulevard of Broken Dreams"]

    lyrics = get_lyrics(ARTISTS, SONGS)
    print(lyrics)

           