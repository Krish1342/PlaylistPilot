import streamlit as st
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from app import AIEnhancedSpotifyGenerator
import json

st.set_page_config(page_title="PlaylistPilot", page_icon="🎧")

# Use Streamlit secrets for environment variables
def get_env_var(key, default=None):
    try:
        return st.secrets[key]
    except KeyError:
        return default

# Validate required secrets
required_secrets = ["SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "SPOTIPY_REDIRECT_URI", "GEMINI_API_KEY", "AUTH_SERVER_URL"]
missing_secrets = [secret for secret in required_secrets if not get_env_var(secret)]

if missing_secrets:
    st.error(f"Missing required secrets: {', '.join(missing_secrets)}")
    st.info("Please add these secrets in your Streamlit Community Cloud dashboard.")
    st.stop()

AUTH_SERVER_URL = get_env_var("AUTH_SERVER_URL")

# Token management via API calls to Flask server
def get_token_from_server(username):
    """Get token from Flask auth server"""
    try:
        response = requests.get(f"{AUTH_SERVER_URL}/get_token/{username}")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Error connecting to auth server: {e}")
        return None

def store_token_on_server(username, token_info):
    """Store token on Flask auth server"""
    try:
        response = requests.post(f"{AUTH_SERVER_URL}/store_token", json={
            "username": username,
            "token_info": token_info
        })
        return response.status_code == 200
    except Exception as e:
        st.error(f"Error storing token: {e}")
        return False

# Get username from query parameters
username = st.query_params.get("user")

st.title("🎧 PlaylistPilot")
st.markdown("*AI-powered Spotify playlist generator*")

if not username:
    st.subheader("🔐 Login to Get Started")
    username = st.text_input("Enter your Spotify username or nickname:", 
                           placeholder="e.g., john_doe")
    
    if username:
        login_url = f"{AUTH_SERVER_URL}/login/{username}"
        st.markdown(f"""
        ### Ready to generate your AI playlist?
        
        Click the button below to authenticate with Spotify:
        
        <a href="{login_url}" target="_blank">
            <button style="
                background-color: #1DB954;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 50px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                margin: 10px 0;
            ">🎵 Connect with Spotify</button>
        </a>
        
        *After authentication, you'll be redirected back here.*
        """, unsafe_allow_html=True)
    
    st.info("💡 **How it works:**\n- Connect your Spotify account\n- AI analyzes your music taste\n- Get a personalized playlist created just for you!")
    st.stop()

# Check authentication status
st.subheader(f"👋 Welcome back, {username}!")

# For Streamlit Cloud, we'll use a simpler approach without the Flask token API
# since we can't easily share the database between services
if 'spotify_client' not in st.session_state:
    st.warning("⚠️ Authentication required")
    st.markdown(f"""
    Please click the link below to authenticate:
    
    <a href="{AUTH_SERVER_URL}/login/{username}" target="_blank">
        <button style="
            background-color: #1DB954;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 25px;
            font-size: 14px;
            cursor: pointer;
        ">🔄 Re-authenticate with Spotify</button>
    </a>
    """, unsafe_allow_html=True)
    
    # Manual token input as fallback
    st.markdown("---")
    st.subheader("🔧 Manual Token Input")
    st.markdown("If you have authentication issues, you can manually enter your Spotify access token:")
    
    manual_token = st.text_input("Spotify Access Token:", type="password", 
                                help="Get this from the Spotify Web API Console or your browser's developer tools")
    
    if manual_token:
        try:
            sp = spotipy.Spotify(auth=manual_token)
            user_profile = sp.me()
            st.session_state.spotify_client = sp
            st.success(f"✅ Manually authenticated as {user_profile['display_name']}!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Invalid token: {e}")
    
    st.stop()

# Use the authenticated Spotify client
sp = st.session_state.spotify_client

# Display user info
try:
    user_profile = sp.me()
    st.success(f"✅ Connected as **{user_profile['display_name']}**")
except Exception as e:
    st.error("❌ Authentication expired. Please re-authenticate.")
    if st.button("🔄 Re-authenticate"):
        del st.session_state.spotify_client
        st.rerun()
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
        client_id=get_env_var("SPOTIPY_CLIENT_ID"),
        client_secret=get_env_var("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=get_env_var("SPOTIPY_REDIRECT_URI"),
        gemini_api_key=get_env_var("GEMINI_API_KEY")
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
                st.balloons()
                st.success("🎉 Playlist created successfully!")
                
                # Display playlist info
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"### 🎵 {playlist['name']}")
                    st.markdown(f"📝 {playlist.get('description', 'AI-generated playlist')}")
                
                with col2:
                    st.markdown(f"[🎧 **Open in Spotify**]({playlist['external_urls']['spotify']})")
                    st.markdown(f"**Tracks:** {playlist.get('tracks', {}).get('total', 'N/A')}")
                
                # Show some additional info
                st.info("🤖 Your playlist has been created using AI analysis of your music taste. Check your Spotify app to see the full playlist!")
                
                # Option to generate another
                if st.button("🔄 Generate Another Playlist"):
                    st.rerun()
                
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
st.markdown("Made with ❤️ using Streamlit • [Source Code](https://github.com/your-username/playlist-pilot)")