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

# Validate required environment variables
def validate_environment():
    required_vars = ["SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "SPOTIPY_REDIRECT_URI", "GEMINI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        st.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        st.stop()

validate_environment()

# Use consistent database path
DB_PATH = str(pathlib.Path(__file__).parent.resolve() / "spotify_tokens.db")

def init_db():
    """Initialize the database connection"""
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
    """Store token information in the database"""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO tokens (username, access_token, refresh_token, expires_at)
        VALUES (?, ?, ?, ?)
    """, (username, token_info['access_token'], token_info['refresh_token'], token_info['expires_at']))
    conn.commit()

def get_token(conn, username):
    """Retrieve token information from the database"""
    cursor = conn.cursor()
    cursor.execute("SELECT access_token, refresh_token, expires_at FROM tokens WHERE username = ?", (username,))
    row = cursor.fetchone()
    if row:
        return {'access_token': row[0], 'refresh_token': row[1], 'expires_at': row[2]}
    return None

class DBTokenHandler:
    """Custom token handler for spotipy that uses database storage"""
    def __init__(self, conn, username):
        self.conn = conn
        self.username = username
    
    def get_cached_token(self):
        return get_token(self.conn, self.username)
    
    def save_token_to_cache(self, token_info):
        store_token(self.conn, self.username, token_info)

# Initialize database
conn = init_db()

# Get username from query parameters (fixed syntax)
username = st.query_params.get("user")

st.title("🎧 PlaylistPilot")

if not username:
    username = st.text_input("Enter your Spotify username or nickname:")
    if username:
       auth_host = os.getenv("AUTH_HOST", "playlistpilot-production.up.railway.app")
       auth_port = os.getenv("AUTH_PORT", "")
       auth_url = f"https://{auth_host}/login/{username}" if not auth_port else f"http://{auth_host}:{auth_port}/login/{username}"
       st.markdown(f"[🔐 Click here to log in]({auth_url})")
    st.stop()

# Check for existing token
token_info = get_token(conn, username)
if not token_info:
    st.error("Token not found. Please login again.")
    auth_host = os.getenv("AUTH_HOST", "127.0.0.1")
    auth_port = os.getenv("AUTH_PORT", "8080")
    st.markdown(f"[🔐 Re-login here](http://{auth_host}:{auth_port}/login/{username})")
    st.stop()

# Set up Spotify OAuth with database token handler
sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="user-top-read playlist-modify-public playlist-modify-private user-library-read user-read-recently-played user-follow-read"
)
sp_oauth.cache_handler = DBTokenHandler(conn, username)

# Try to refresh token and create Spotify client
try:
    # Refresh the token if needed
    if 'refresh_token' in token_info:
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        store_token(conn, username, token_info)
    
    # Create Spotify client
    sp = spotipy.Spotify(auth=token_info['access_token'])
    
    # Test the connection
    user_profile = sp.me()
    st.success(f"Welcome, {user_profile['display_name']}!")
    
except Exception as e:
    st.error(f"Failed to authenticate with Spotify: {e}")
    st.error("Please try logging in again.")
    auth_host = os.getenv("AUTH_HOST", "127.0.0.1")
    auth_port = os.getenv("AUTH_PORT", "8080")
    st.markdown(f"[🔐 Re-login here](http://{auth_host}:{auth_port}/login/{username})")
    st.stop()

# Playlist customization UI
st.subheader("🎨 Customize Your Playlist")

col1, col2 = st.columns(2)
with col1:
    mood = st.text_input("Mood (optional)", placeholder="e.g., energetic, chill, melancholic")
    theme = st.text_input("Theme (optional)", placeholder="e.g., summer vibes, workout, study")

with col2:
    occasion = st.text_input("Occasion (optional)", placeholder="e.g., party, road trip, relaxing")
    playlist_size = st.slider("Number of tracks", 10, 50, 25, 5)

# Time range selection
time_range_options = {
    "Last 4 weeks": "short_term",
    "Last 6 months": "medium_term", 
    "All time": "long_term"
}
time_range_display = st.selectbox("Base playlist on", list(time_range_options.keys()), index=1)
time_range = time_range_options[time_range_display]

# Initialize the AI generator
@st.cache_resource
def get_generator():
    return AIEnhancedSpotifyGenerator(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        gemini_api_key=os.getenv("GEMINI_API_KEY")
    )

generator = get_generator()
generator.sp = sp  # Set the authenticated Spotify client

# Generate playlist button
if st.button("🚀 Generate AI Playlist", type="primary"):
    with st.spinner("🤖 AI is analyzing your music taste and generating playlist..."):
        try:
            # Generate the playlist
            playlist = generator.generate_ai_enhanced_playlist(
                playlist_size=playlist_size,
                time_range=time_range,
                mood=mood if mood else None,
                theme=theme if theme else None,
                occasion=occasion if occasion else None
            )
            
            if playlist:
                st.success("🎉 Playlist created successfully!")
                
                # Display playlist info
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"### 🎵 {playlist['name']}")
                    st.markdown(f"📝 {playlist.get('description', 'AI-generated playlist')}")
                
                with col2:
                    st.markdown(f"[🎧 Open in Spotify]({playlist['external_urls']['spotify']})")
                    st.markdown(f"**Tracks:** {playlist.get('tracks', {}).get('total', 'N/A')}")
                
                # Show some additional info
                st.info("🤖 Your playlist has been created using AI analysis of your music taste. Check your Spotify app to see the full playlist!")
                
            else:
                st.error("❌ Failed to generate playlist. This could be due to:")
                st.markdown("""
                - Insufficient listening history on Spotify
                - API rate limits
                - Network issues
                - AI service unavailable
                
                Please try again or contact support if the issue persists.
                """)
                
        except Exception as e:
            st.error(f"❌ Error generating playlist: {str(e)}")
            st.markdown("**Troubleshooting tips:**")
            st.markdown("""
            - Make sure you have listened to enough music on Spotify
            - Check your internet connection
            - Try again in a few minutes
            - Verify your API credentials are correct
            """)

# Display user's music stats (optional)
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

# Footer
st.markdown("---")
st.markdown("🤖 Powered by AI and the Spotify Web API")
st.markdown("Made with ❤️ using Streamlit")

# Close database connection when done
if st.session_state.get('cleanup_db', False):
    conn.close()