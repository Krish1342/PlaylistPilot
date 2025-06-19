from flask import Flask, redirect, request
from spotipy.oauth2 import SpotifyOAuth
import os
import sqlite3
from dotenv import load_dotenv
import pathlib

load_dotenv()
app = Flask(__name__)

# Use environment variables with fallbacks
DB_PATH = os.getenv('DATABASE_PATH', str(pathlib.Path(__file__).parent.resolve() / "spotify_tokens.db"))
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
STREAMLIT_URL = os.getenv("STREAMLIT_URL", "http://localhost:8501")

def store_token(username, token_info):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            username TEXT PRIMARY KEY,
            access_token TEXT,
            refresh_token TEXT,
            expires_at INTEGER
        )
    """)
    cursor.execute("""
        INSERT OR REPLACE INTO tokens (username, access_token, refresh_token, expires_at)
        VALUES (?, ?, ?, ?)
    """, (
        username,
        token_info['access_token'],
        token_info['refresh_token'],
        token_info['expires_at']
    ))
    conn.commit()
    conn.close()

@app.route("/")
def home():
    return """
    <h1>Spotify Auth Server</h1>
    <p>This server handles Spotify authentication for PlaylistPilot.</p>
    <p><a href="{}">Go to PlaylistPilot App</a></p>
    """.format(STREAMLIT_URL)

@app.route("/login/<username>")
def login(username):
    sp_oauth = SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=REDIRECT_URI,
        scope="user-top-read playlist-modify-public playlist-modify-private user-library-read user-read-recently-played user-follow-read",
        cache_path=None,
        show_dialog=True
    )
    auth_url = sp_oauth.get_authorize_url(state=username)
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    username = request.args.get("state")
    
    if not code or not username:
        return "Error: Missing code or username", 400
    
    sp_oauth = SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=REDIRECT_URI,
        scope="user-top-read playlist-modify-public playlist-modify-private user-library-read user-read-recently-played user-follow-read",
        cache_path=None
    )
    
    try:
        token_info = sp_oauth.get_access_token(code, as_dict=True)
        store_token(username, token_info)
        return redirect(f"{STREAMLIT_URL}/?user={username}")
    except Exception as e:
        return f"Error getting token: {str(e)}", 500

@app.route("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)