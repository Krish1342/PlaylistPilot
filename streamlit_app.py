import streamlit as st
import os
import sqlite3
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pathlib
from app import AIEnhancedSpotifyGenerator

st.set_page_config(page_title="PlaylistPilot", page_icon="🎧")
load_dotenv()

def validate_environment():
    required_vars = ["SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "SPOTIPY_REDIRECT_URI", "GEMINI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        st.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        st.stop()

validate_environment()

DB_PATH = str(pathlib.Path(__file__).parent.resolve() / "spotify_tokens.db")

def init_db():
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
    conn.commit()
    return conn

def store_token(conn, username, token_info):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO tokens (username, access_token, refresh_token, expires_at)
        VALUES (?, ?, ?, ?)
    """, (username, token_info['access_token'], token_info['refresh_token'], token_info['expires_at']))
    conn.commit()

def get_token(conn, username):
    cursor = conn.cursor()
    cursor.execute("SELECT access_token, refresh_token, expires_at FROM tokens WHERE username = ?", (username,))
    row = cursor.fetchone()
    if row:
        return {'access_token': row[0], 'refresh_token': row[1], 'expires_at': row[2]}
    return None

class DBTokenHandler:
    def __init__(self, conn, username):
        self.conn = conn
        self.username = username

    def get_cached_token(self):
        return get_token(self.conn, self.username)

    def save_token_to_cache(self, token_info):
        store_token(self.conn, self.username, token_info)

conn = init_db()
username = st.query_params.get("user")
st.title("🎧 PlaylistPilot")

if not username:
    username = st.text_input("Enter your Spotify username or nickname:")
    if username:
        auth_host = os.getenv("AUTH_HOST", "127.0.0.1")
        auth_port = os.getenv("AUTH_PORT", "8080")
        auth_url = f"http://{auth_host}:{auth_port}/login/{username}"
        st.markdown(f"[🔐 Click here to log in]({auth_url})")
    st.stop()

token_info = get_token(conn, username)
if not token_info:
    st.error("Token not found. Please login again.")
    auth_host = os.getenv("AUTH_HOST", "127.0.0.1")
    auth_port = os.getenv("AUTH_PORT", "8080")
    st.markdown(f"[🔐 Re-login here](http://{auth_host}:{auth_port}/login/{username})")
    st.stop()

sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="user-top-read playlist-modify-public playlist-modify-private user-library-read user-read-recently-played user-follow-read"
)
sp_oauth.cache_handler = DBTokenHandler(conn, username)

try:
    if 'refresh_token' in token_info:
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        store_token(conn, username, token_info)
    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_profile = sp.me()
    st.success(f"Welcome, {user_profile['display_name']}!")
except Exception as e:
    st.error(f"Failed to authenticate with Spotify: {e}")
    auth_host = os.getenv("AUTH_HOST", "127.0.0.1")
    auth_port = os.getenv("AUTH_PORT", "8080")
    st.markdown(f"[🔐 Re-login here](http://{auth_host}:{auth_port}/login/{username})")
    st.stop()

@st.cache_resource
def get_generator():
    return AIEnhancedSpotifyGenerator(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        gemini_api_key=os.getenv("GEMINI_API_KEY")
    )

generator = get_generator()
generator.sp = sp

st.subheader("🎨 Customize Your Playlist")

col1, col2 = st.columns(2)
with col1:
    mood = st.text_input("Mood (optional)", placeholder="e.g., energetic, chill, melancholic", key="mood")
    theme = st.text_input("Theme (optional)", placeholder="e.g., summer vibes, workout, study", key="theme")
with col2:
    occasion = st.text_input("Occasion (optional)", placeholder="e.g., party, road trip, relaxing", key="occasion")
    playlist_size = st.slider("Number of tracks", 10, 50, 25, 5, key="size")

time_range_options = {
    "Last 4 weeks": "short_term",
    "Last 6 months": "medium_term",
    "All time": "long_term"
}
time_range_display = st.selectbox("Base playlist on", list(time_range_options.keys()), index=1, key="time_range_display")
time_range = time_range_options[time_range_display]

if "playlist_data" not in st.session_state and st.button("🚀 Generate AI Playlist", type="primary"):
    with st.spinner("🤖 AI is analyzing your music taste and preparing suggestions..."):
        try:
            playlist_data = generator.prepare_ai_playlist_preview(
                playlist_size=playlist_size,
                time_range=time_range,
                mood=mood if mood else None,
                theme=theme if theme else None,
                occasion=occasion if occasion else None
            )
            if playlist_data:
                st.session_state.playlist_data = playlist_data
            else:
                st.error("❌ AI failed to generate playlist. Try again later.")
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")

if "playlist_data" in st.session_state:
    playlist_data = st.session_state.playlist_data
    suggested_tracks = [track['track'] for track in playlist_data.get("selected_tracks", [])]

    st.subheader("✅ Suggested Playlist Tracks")
    for i, track in enumerate(suggested_tracks, 1):
        st.write(f"{i}. {track['name']} - {', '.join([a['name'] for a in track['artists']])}")

    playlist_name = st.text_input("Playlist Name", value=playlist_data['playlist_name'], key="playlist_name_input")
    description = playlist_data.get('description', '')

    update_existing = st.checkbox("Update an existing playlist instead of creating new one", key="update_existing")
    selected_playlist = None

    if update_existing:
        playlists = sp.current_user_playlists(limit=50)['items']
        playlist_options = {pl['name']: pl['id'] for pl in playlists}
        selected_name = st.selectbox("Choose a playlist to update", list(playlist_options.keys()), key="playlist_select")
        selected_playlist = playlist_options[selected_name]

    if st.button("✅ Confirm and Proceed", key="confirm_proceed"):
        try:
            uris = [track['uri'] for track in suggested_tracks]
            st.write("URIs to be added:", uris)
            st.write("Track count:", len(uris))

            if update_existing and selected_playlist:
                sp.playlist_add_items(selected_playlist, uris)
                st.success(f"✅ Songs successfully added to '{selected_name}'!")
            else:
                new_playlist = generator.create_playlist(
                    user_id=playlist_data['user_id'],
                    playlist_name=playlist_name,
                    track_uris=uris,
                    description=description
                )
                if new_playlist:
                    st.success(f"🎉 Playlist '{playlist_name}' created successfully!")
                    st.markdown(f"[🎧 Open in Spotify]({new_playlist['external_urls']['spotify']})")
                else:
                    st.error("❌ Playlist creation failed. Please try again.")
                    st.write("Returned playlist object:", new_playlist)
        except Exception as e:
            st.error("Playlist creation crashed.")
            st.write(str(e))

    if st.button("🔄 Start Over", key="reset"):
        st.session_state.pop("playlist_data", None)
        st.experimental_rerun()

with st.expander("📊 Your Music Stats", expanded=False):
    try:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🎤 Top Artists")
            top_artists = sp.current_user_top_artists(limit=5, time_range=time_range)
            for i, artist in enumerate(top_artists['items'], 1):
                st.write(f"{i}. {artist['name']}")
        with col2:
            st.subheader("🎵 Top Tracks")
            top_tracks = sp.current_user_top_tracks(limit=5, time_range=time_range)
            for i, track in enumerate(top_tracks['items'], 1):
                st.write(f"{i}. {track['name']} - {track['artists'][0]['name']}")
    except Exception as e:
        st.error(f"Could not load music stats: {e}")

st.markdown("---")
st.markdown("🤖 Powered by AI and the Spotify Web API")
st.markdown("Made with ❤ using Streamlit")

if st.session_state.get('cleanup_db', False):
    conn.close()
