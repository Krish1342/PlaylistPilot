from flask import Flask, redirect, request
from spotipy.oauth2 import SpotifyOAuth
import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
import pathlib
DB_PATH = str(pathlib.Path(__file__).parent.resolve() / "spotify_tokens.db")

REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8080/callback")

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
    sp_oauth = SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=REDIRECT_URI,
        scope="user-top-read playlist-modify-public playlist-modify-private user-library-read user-read-recently-played user-follow-read",
        cache_path=None
    )
    token_info = sp_oauth.get_access_token(code, as_dict=True)
    store_token(username, token_info)
    return redirect(f"http://localhost:8501/?user={username}")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
