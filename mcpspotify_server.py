
import requests
import json
import base64
import os
import sys
import urllib.parse
from dotenv import load_dotenv
from http.server import BaseHTTPRequestHandler, HTTPServer
import webbrowser
from dataclasses import dataclass
from mcp.server.fastmcp import FastMCP, Context
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SCOPE = "user-read-private playlist-modify-public playlist-modify-private"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"



class SpotifyAuthHandler(BaseHTTPRequestHandler):
    auth_code = None
    def do_GET(self):
        # global auth_code
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)

        if "code" in query_params:
            SpotifyAuthHandler.auth_code = query_params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>You may now close this window.</h1>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h1>Authorization failed.</h1>")



class SpotifySession:
    def __init__(self, client_id, client_secret, redirect_uri, token_path="tokens.json"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_path = token_path
        self.auth_code = None
        self.tokens = None
        

    def get_auth_url(self):
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": SCOPE,
        }


        query_string = urllib.parse.urlencode(params)
        auth_url = f"{AUTH_URL}?{query_string}"

        print("Go to this URL in your browser:")
        print(auth_url)
        return auth_url
    
    def user_authenticate(self):
        #start a local server
        server = HTTPServer(("localhost", 8888), SpotifyAuthHandler)
        print('Starting local server at localhost:8888')
        # Wait for redirect
        while SpotifyAuthHandler.auth_code is None:
            server.handle_request()  # handles one request and exits
        self.auth_code = SpotifyAuthHandler.auth_code
        # return SpotifyAuthHandler.auth_code

        
    def authcode_exch_accesscode(self):
        data = {
            "grant_type": "authorization_code",
            "code": self.auth_code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        response = requests.post(TOKEN_URL, data=data)
        # response.raise_for_status()
        self.tokens = response.json()
        # return response.json()

    def refresh_access_token(self):
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.tokens['refresh_token'],
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        response = requests.post(TOKEN_URL, data=data)
        if response.status_code != 200:
            print("Failed to refresh token:", response.status_code, response.text)
            return None
        
        self.tokens['access_token'] = response.json()["access_token"] #instead of returning the access token to somewhere, we just saved the access token to the class attribute, so it becomes available to all methods of this class without it passing around
        self.save_tokens()
    
    def get_access_token(self):
        #we refresh before we return the access token
        self.refresh_access_token()
        return self.tokens['access_token']

    def save_tokens(self):
        with open(self.token_path, "w") as f:
            json.dump(self.tokens, f)

    def load_tokens(self):
        with open(self.token_path, "r") as f:
            self.tokens = json.load(f)

@dataclass
class SpotifyContext:
    session: SpotifySession

@asynccontextmanager
async def spotify_lifespan(server: FastMCP) -> AsyncIterator[SpotifyContext]:
    
    session = SpotifySession(
        client_id=os.getenv("CLIENT_ID"),
        client_secret = os.getenv("CLIENT_SECRET"),
        redirect_uri=os.getenv('REDIRECT_URI')
    )

    try:
        session.load_tokens()
    except FileNotFoundError:
        print("No token file found. Starting authorization flow.")
        print("Visit this URL to authorize:")
        print(session.get_auth_url())
        webbrowser.open(session.get_auth_url())
        session.user_authenticate()
        session.authcode_exch_accesscode()

    yield SpotifyContext(session)


mcp = FastMCP(
    "mcp-spotify",
    dependencies=[
        "requests", "python-dotenv", "mcp",  # anything else you import
    ],
    lifespan = spotify_lifespan
)

@mcp.tool()
def get_user_id(ctx: Context = None) -> str:
    """
    Retrieve the current Spotify user's unique user ID.

    This tool fetches the authenticated user's Spotify account ID,
    which is required for operations like creating a playlist.

    Returns:
        The Spotify user ID (a string).
    """

    session = ctx.request_context.lifespan_context.session
    access_token = session.get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://api.spotify.com/v1/me", headers=headers)
    # print(res.json())  # contain 'id', 'email', etc.
    user = res.json()
    user_id = user['id']
    return user_id

@mcp.tool()
def get_song_id(name: str, ctx: Context = None) -> str:
    """
    Search for a track on Spotify by its name and return its unique Spotify URI.

    Args:
        name: The name of the song (can include artist for better accuracy, e.g. "Chura Ke Dil Mera Kumar Sanu").

    Returns:
        The Spotify URI of the top matching track (e.g. "spotify:track:7v5zr1r0ft1LX2pIjHXopK").

    Note:
        This tool uses Spotify's search API and returns the best match.
        If multiple songs match the name, it selects the first result.
    """

    session = ctx.request_context.lifespan_context.session
    access_token = session.get_access_token()
    queryParams = '?q={}&type=track&market=IN&limit=1'.format(urllib.parse.quote(name))
    # print(queryParams)
    headers={"Authorization":f"Bearer {access_token}"}
    r = requests.get('https://api.spotify.com/v1/search' + queryParams, headers=headers)
    res = r.json()
    return res['tracks']['items'][0]['uri']

#helper implementations
def helper_get_user_id(session: SpotifySession) -> str:
    # session = ctx.request_context.lifespan_context.session
    access_token = session.get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://api.spotify.com/v1/me", headers=headers)
    # print(res.json())  # contain 'id', 'email', etc.
    user = res.json()
    user_id = user['id']
    return user_id

def helper_get_song_id(name: str, session: SpotifySession) -> str:
    # session = ctx.request_context.lifespan_context.session
    access_token = session.get_access_token()
    queryParams = '?q={}&type=track&market=IN&limit=1'.format(urllib.parse.quote(name))
    # print(queryParams)
    headers={"Authorization":f"Bearer {access_token}"}
    r = requests.get('https://api.spotify.com/v1/search' + queryParams, headers=headers)
    res = r.json()
    return res['tracks']['items'][0]['uri']


@mcp.tool()
def create_playlist(playlistname: str, 
                    description: str, 
                    ctx: Context = None) -> dict:
    """
    Create a new private playlist for the current Spotify user.

    Args:
        playlistname: The title of the playlist to be created.
        description: A brief description for the playlist.

    Returns:
        A dictionary containing:
            - playlist_id: The unique ID of the created playlist. This will be used in the add_tracks_playlist(playlist_id, ....) function
            - playlist_url: The public Spotify link to the playlist.
            - name: The playlist name.
            - status: '201' if successful.
    
    This playlist is created as private (not visible to followers by default, users can use the public link to share the playlist).

    """

    session = ctx.request_context.lifespan_context.session
    user_id = helper_get_user_id(session)
    access_token = session.get_access_token()
    playlist_endpoint_url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    request_body = json.dumps({
            "name": playlistname,
            "description": description,
            "public": False
        })
    headers={"Content-Type":"application/json", 
                        "Authorization":f"Bearer {access_token}"}
    response = requests.post(url =playlist_endpoint_url, data = request_body, headers=headers)
    # response.json()
    # url = response.json()['external_urls']['spotify']
    # print(response.status_code)
    # playlist_url = response.json()['external_urls']['spotify']
    # playlist_id = response.json()['id']
    return {
        'playlist_id': response.json()['id'],
        'playlist_url': response.json()['external_urls']['spotify'],
        "name": response.json()["name"],
        "status": "201"
    }

# @mcp.tool()
def helper_songs_uri_list(song_list: list, 
                   session: SpotifySession) -> list:

    # session = ctx.request_context.lifespan_context.session
    # access_token = session.get_access_token()
    uris = []
    for song in song_list:
        uris.append(helper_get_song_id(song, session))
    return uris

@mcp.tool()
def add_tracks_playlist(playlist_id: str, 
                        song_list: list, 
                        ctx: Context) -> dict:
    
    """
     Add a list of songs (list can contain 1 or more songs) to a Spotify playlist.

    Args:

        playlist_id: The Spotify ID of the target playlist (use the one from the output from create_playlist function).
        song_list: A list of :
            - Song names (e.g. ["Chura Ke Dil Mera", "Hanuman Chalisa", "In The End"])
            

    Returns:
        A dictionary response from Spotify, including a snapshot_id confirming changes.

    Notes:
        - If a song name is passed, the tool performs a search to resolve the correct URI.
        - DO not pass URI in the song_list.
        # - If a URI is passed, it is added directly without searching.
        # - Invalid songs or inaccessible tracks may be skipped without error.
    """

    session = ctx.request_context.lifespan_context.session
    
    print("Adding these Songs", song_list, file=sys.stderr, flush=True)
    uris = helper_songs_uri_list(song_list, session)
    print("Adding these URIs", uris, file=sys.stderr, flush=True)
    with open("debug_uris.log", "w") as f:
        f.write(json.dumps(uris, indent=2))
    
    access_token = session.get_access_token()
    playlist_track_endpoint_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    request_body = json.dumps({
        "uris" : uris #URIs of songs to be added
    })
    headers={"Content-Type":"application/json", 
                            "Authorization":f"Bearer {access_token}"}
    response = requests.post(url =playlist_track_endpoint_url, data = request_body, headers=headers)
    return response.json()

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio') 
