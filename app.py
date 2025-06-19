import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import numpy as np
import google.generativeai as genai
import json
import re
from datetime import datetime, timedelta
import logging
import random
from collections import Counter
import time
import os
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")
gemini_api_key = os.getenv("GEMINI_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIEnhancedSpotifyGenerator:
    def __init__(self, client_id, client_secret, redirect_uri, gemini_api_key, spotify_client=None):
        """
        Initialize the AI-Enhanced Spotify Playlist Generator with Gemini AI
        
        Args:
            client_id (str): Spotify API client ID
            client_secret (str): Spotify API client secret
            redirect_uri (str): Redirect URI for OAuth
            gemini_api_key (str): Google Gemini API key
            spotify_client (spotipy.Spotify): Optional existing Spotify client
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        
        # Use provided Spotify client or None (will be set later)
        self.sp = spotify_client
        
        # Initialize Gemini AI only if API key is provided
        if gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.ai_enabled = True
                logger.info("AI features enabled with Gemini")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini AI: {e}")
                self.model = None
                self.ai_enabled = False
        else:
            logger.warning("No Gemini API key provided, AI features disabled")
            self.model = None
            self.ai_enabled = False
        
        # Set up Spotify authentication scope
        self.scope = "user-top-read playlist-modify-public playlist-modify-private user-library-read user-read-recently-played user-follow-read"

    def authenticate_user(self, username=None):
        """
        Authenticate a new user with Spotify and return a Spotipy client.
        This method is for standalone usage, not for Streamlit integration.
        """
        if not username:
            username = f"user_{int(time.time())}"  # fallback unique ID

        cache_path = f".cache-{username}"  # unique token cache per user

        auth_manager = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            cache_path=cache_path,
            open_browser=True
        )
        return spotipy.Spotify(auth_manager=auth_manager)

    def get_user_profile(self):
        """Get current user's Spotify profile"""
        try:
            if not self.sp:
                logger.error("No Spotify client available")
                return None
            
            user = self.sp.current_user()
            logger.info(f"Connected to Spotify account: {user['display_name']}")
            return user
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None
    
    def get_top_artists(self, time_range='medium_term', limit=50):
        """Get user's top artists"""
        try:
            if not self.sp:
                return []
            results = self.sp.current_user_top_artists(time_range=time_range, limit=limit)
            return results['items']
        except Exception as e:
            logger.error(f"Error getting top artists: {e}")
            return []
    
    def get_top_tracks(self, time_range='medium_term', limit=50):
        """Get user's top tracks"""
        try:
            if not self.sp:
                return []
            results = self.sp.current_user_top_tracks(time_range=time_range, limit=limit)
            return results['items']
        except Exception as e:
            logger.error(f"Error getting top tracks: {e}")
            return []
    
    def get_recently_played(self, limit=50):
        """Get user's recently played tracks"""
        try:
            if not self.sp:
                return []
            results = self.sp.current_user_recently_played(limit=limit)
            return results['items']
        except Exception as e:
            logger.error(f"Error getting recently played: {e}")
            return []
    
    def get_saved_tracks(self, limit=50):
        """Get user's saved/liked tracks"""
        try:
            if not self.sp:
                return []
            results = self.sp.current_user_saved_tracks(limit=limit)
            return results['items']
        except Exception as e:
            logger.error(f"Error getting saved tracks: {e}")
            return []
    
    def analyze_music_with_ai(self, top_artists, top_tracks, recently_played=None):
        """
        Use Gemini AI to analyze user's music taste and provide insights
        """
        if not self.ai_enabled:
            return self.fallback_analysis(top_artists, top_tracks)
        
        try:
            # Prepare data for AI analysis
            artist_data = []
            for artist in top_artists[:20]:  # Limit to top 20 artists
                artist_data.append({
                    'name': artist['name'],
                    'genres': artist.get('genres', []),
                    'popularity': artist.get('popularity', 0)
                })
            
            track_data = []
            for track in top_tracks[:20]:  # Limit to top 20 tracks
                track_data.append({
                    'name': track['name'],
                    'artist': track['artists'][0]['name'],
                    'album': track['album']['name'],
                    'release_date': track['album'].get('release_date', ''),
                    'popularity': track.get('popularity', 0)
                })
            
            # Create AI prompt
            prompt = f"""
            Analyze this user's music taste based on their top artists and tracks. Provide insights and recommendations.

            TOP ARTISTS: {json.dumps(artist_data, indent=2)}
            
            TOP TRACKS: {json.dumps(track_data, indent=2)}
            
            Please provide a detailed analysis in the following JSON format:
            {{
                "music_personality": "Brief description of their music personality",
                "primary_genres": ["genre1", "genre2", "genre3"],
                "mood_preferences": ["mood1", "mood2", "mood3"],
                "discovery_suggestions": {{
                    "similar_artists": ["artist1", "artist2", "artist3"],
                    "genre_exploration": ["genre1", "genre2"],
                    "era_preferences": ["era1", "era2"]
                }},
                "playlist_themes": [
                    {{"name": "Theme Name", "description": "Theme description", "search_terms": ["term1", "term2"]}},
                    {{"name": "Theme Name 2", "description": "Theme description", "search_terms": ["term1", "term2"]}}
                ],
                "creative_insights": "Unique observations about their music taste",
                "recommended_search_strategies": ["strategy1", "strategy2", "strategy3"]
            }}
            
            Make sure to provide specific, actionable insights that can help discover new music.
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse AI response
            ai_analysis = self.parse_ai_response(response.text)
            logger.info("AI analysis completed successfully")
            return ai_analysis
            
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return self.fallback_analysis(top_artists, top_tracks)
    
    def parse_ai_response(self, response_text):
        """Parse AI response and extract JSON"""
        try:
            # Look for JSON in the response
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON without code blocks
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("No JSON found in response")
            
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return self.fallback_analysis([], [])
    
    def fallback_analysis(self, top_artists, top_tracks):
        """Fallback analysis if AI fails"""
        genres = Counter()
        for artist in top_artists:
            for genre in artist.get('genres', []):
                genres[genre] += 1
        
        return {
            "music_personality": "Diverse music listener with varied tastes",
            "primary_genres": [genre for genre, _ in genres.most_common(3)],
            "mood_preferences": ["energetic", "chill", "upbeat"],
            "discovery_suggestions": {
                "similar_artists": [artist['name'] for artist in top_artists[:3]],
                "genre_exploration": [genre for genre, _ in genres.most_common(2)],
                "era_preferences": ["2020s", "2010s"]
            },
            "playlist_themes": [
                {"name": "Discovery Mix", "description": "New tracks based on your taste", "search_terms": ["new music", "trending"]}
            ],
            "creative_insights": "Based on your listening history, you enjoy a mix of popular and emerging artists.",
            "recommended_search_strategies": ["genre-based", "artist-similar", "year-based"]
        }
    
    def generate_ai_playlist_concept(self, mood=None, theme=None, occasion=None):
        """
        Use AI to generate creative playlist concepts
        """
        if not self.ai_enabled:
            return {
                "playlist_name": f"Discovery Mix - {datetime.now().strftime('%Y-%m-%d')}",
                "description": "Curated playlist based on your music taste",
                "target_mood": "balanced",
                "search_queries": ["new music", "trending", "indie"],
                "genre_focus": ["pop", "alternative"],
                "energy_level": "medium",
                "creative_elements": ["discovery", "variety"]
            }
        
        try:
            prompt = f"""
            Create a creative playlist concept based on the following parameters:
            - Mood: {mood or 'Any'}
            - Theme: {theme or 'Any'}
            - Occasion: {occasion or 'Any'}
            
            Provide a response in JSON format:
            {{
                "playlist_name": "Creative playlist name",
                "description": "Detailed description of the playlist concept",
                "target_mood": "The mood this playlist should evoke",
                "search_queries": ["search1", "search2", "search3", "search4", "search5"],
                "genre_focus": ["genre1", "genre2"],
                "energy_level": "high/medium/low",
                "creative_elements": ["element1", "element2"]
            }}
            
            Make the concept unique and engaging.
            """
            
            response = self.model.generate_content(prompt)
            concept = self.parse_ai_response(response.text)
            
            return concept
            
        except Exception as e:
            logger.error(f"Error generating AI playlist concept: {e}")
            return {
                "playlist_name": f"AI Discovery - {datetime.now().strftime('%Y-%m-%d')}",
                "description": "AI-curated playlist based on your music taste",
                "target_mood": "balanced",
                "search_queries": ["new music", "trending", "indie"],
                "genre_focus": ["pop", "alternative"],
                "energy_level": "medium",
                "creative_elements": ["discovery", "variety"]
            }
    
    def enhance_search_with_ai(self, ai_analysis, user_preferences):
        """
        Use AI insights to create smarter search queries
        """
        search_queries = []
        
        # Use AI-recommended search strategies
        for strategy in ai_analysis.get('recommended_search_strategies', []):
            if strategy == "genre-based":
                for genre in ai_analysis.get('primary_genres', []):
                    search_queries.append(f'genre:"{genre}"')
                    search_queries.append(f'{genre} 2024')
            
            elif strategy == "artist-similar":
                for artist in ai_analysis.get('discovery_suggestions', {}).get('similar_artists', []):
                    search_queries.append(f'artist:"{artist}"')
            
            elif strategy == "mood-based":
                for mood in ai_analysis.get('mood_preferences', []):
                    search_queries.append(f'{mood} music')
        
        # Add AI-suggested playlist themes
        for theme in ai_analysis.get('playlist_themes', []):
            search_queries.extend(theme.get('search_terms', []))
        
        # Add era-based searches
        for era in ai_analysis.get('discovery_suggestions', {}).get('era_preferences', []):
            search_queries.append(f'{era} music')
        
        return search_queries
    
    def search_tracks_advanced(self, query_params, limit=20):
        """Advanced search using multiple query strategies"""
        if not self.sp:
            return []
        
        all_tracks = []
        
        for query in query_params:
            try:
                results = self.sp.search(q=query, type='track', limit=limit, market='US')
                tracks = results['tracks']['items']
                all_tracks.extend(tracks)
                
                # Add small delay to avoid rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"Search failed for query '{query}': {e}")
                continue
        
        return all_tracks
    
    def score_tracks_with_ai_insights(self, tracks, ai_analysis, user_preferences):
        """
        Score tracks using both traditional methods and AI insights
        """
        scored_tracks = []
        
        for track in tracks:
            score = 0
            factors = []
            
            # Traditional scoring
            track_artists = [artist['name'].lower() for artist in track.get('artists', [])]
            
            # AI-enhanced scoring
            # Check against AI-recommended similar artists
            similar_artists = [artist.lower() for artist in ai_analysis.get('discovery_suggestions', {}).get('similar_artists', [])]
            if any(artist in similar_artists for artist in track_artists):
                score += 15
                factors.append("ai_artist_match")
            
            # Popularity scoring based on AI insights
            if track.get('popularity'):
                if ai_analysis.get('music_personality', '').lower().find('mainstream') != -1:
                    if track['popularity'] > 70:
                        score += 5
                        factors.append("mainstream_match")
                elif ai_analysis.get('music_personality', '').lower().find('indie') != -1:
                    if track['popularity'] < 50:
                        score += 5
                        factors.append("indie_match")
            
            # Release date scoring
            if track.get('album', {}).get('release_date'):
                try:
                    track_year = int(track['album']['release_date'][:4])
                    era_prefs = ai_analysis.get('discovery_suggestions', {}).get('era_preferences', [])
                    
                    for era in era_prefs:
                        if era == "2020s" and track_year >= 2020:
                            score += 3
                            factors.append("era_2020s")
                        elif era == "2010s" and 2010 <= track_year < 2020:
                            score += 3
                            factors.append("era_2010s")
                except (ValueError, TypeError):
                    pass
            
            # Add randomness for discovery
            randomness = random.uniform(0, 3)
            score += randomness
            
            scored_tracks.append({
                'track': track,
                'score': score,
                'factors': factors
            })
        
        return sorted(scored_tracks, key=lambda x: x['score'], reverse=True)
    
    def remove_duplicates_and_user_tracks(self, candidate_tracks, user_tracks):
        """Remove duplicates and tracks user already has"""
        user_track_ids = set()
        
        # Collect user track IDs
        for track_list in user_tracks:
            for item in track_list:
                track = item if 'track' not in item else item['track']
                if track and track.get('id'):
                    user_track_ids.add(track['id'])
        
        # Filter candidates
        seen_ids = set()
        unique_tracks = []
        
        for track_data in candidate_tracks:
            track = track_data['track']
            track_id = track.get('id')
            
            if track_id and track_id not in seen_ids and track_id not in user_track_ids:
                seen_ids.add(track_id)
                unique_tracks.append(track_data)
        
        return unique_tracks
    
    def clean_playlist_name(self, name):
        """
        Clean playlist name to meet Spotify requirements
        """
        if not name:
            return f"AI Playlist {datetime.now().strftime('%m-%d')}"
        
        # Remove or replace problematic characters
        cleaned = re.sub(r'[<>:"/\\|?*]', '', name)  # Remove invalid characters
        cleaned = re.sub(r'\s+', ' ', cleaned)  # Normalize whitespace
        cleaned = cleaned.strip()
        
        # Limit length (Spotify allows up to 100 characters)
        if len(cleaned) > 90:
            cleaned = cleaned[:87] + "..."
        
        # Fallback if name becomes empty
        if not cleaned:
            cleaned = f"AI Playlist {datetime.now().strftime('%m-%d')}"
        
        return cleaned
    
    def create_playlist(self, user_id, playlist_name, track_uris, description=""):
        """Create a new playlist with selected tracks"""
        if not self.sp:
            logger.error("No Spotify client available")
            return None
        
        try:
            # Clean inputs to prevent API errors
            clean_name = self.clean_playlist_name(playlist_name)
            clean_description = description[:300] if description else ""  # Spotify limit
            
            logger.info(f"Creating playlist with name: '{clean_name}'")
            
            # Create playlist
            playlist = self.sp.user_playlist_create(
                user=user_id,
                name=clean_name,
                public=False,
                description=clean_description
            )
            
            logger.info(f"Playlist created successfully: {playlist['id']}")
            
            # Add tracks in batches
            if track_uris:
                for i in range(0, len(track_uris), 100):
                    batch = track_uris[i:i+100]
                    try:
                        self.sp.playlist_add_items(playlist['id'], batch)
                        logger.info(f"Added batch {i//100 + 1}: {len(batch)} tracks")
                    except Exception as batch_error:
                        logger.error(f"Error adding batch {i//100 + 1}: {batch_error}")
                        continue
            
            logger.info(f"Created playlist '{clean_name}' with {len(track_uris)} tracks")
            return playlist
            
        except Exception as e:
            logger.error(f"Error creating playlist: {e}")
            return None
    
    def generate_ai_enhanced_playlist(self, playlist_size=25, time_range='medium_term', 
                                    mood=None, theme=None, occasion=None):
        """
        Main method to generate AI-enhanced smart playlist
        """
        try:
            logger.info("Starting AI-enhanced playlist generation...")
            
            # Get user data
            user = self.get_user_profile()
            if not user:
                logger.error("Could not get user profile")
                return None
            
            # Collect user data
            top_artists = self.get_top_artists(time_range=time_range)
            top_tracks = self.get_top_tracks(time_range=time_range)
            recently_played = self.get_recently_played()
            
            if not top_artists and not top_tracks:
                logger.error("Could not retrieve enough user data")
                return None
            
            # AI Analysis
            logger.info("Analyzing music taste with AI...")
            ai_analysis = self.analyze_music_with_ai(top_artists, top_tracks, recently_played)
            
            # Generate AI playlist concept
            playlist_concept = self.generate_ai_playlist_concept(mood, theme, occasion)
            
            # Create basic user preferences
            user_preferences = {
                'artists': Counter([track['artists'][0]['name'] for track in top_tracks]),
                'genres': Counter()
            }
            
            # Enhanced search with AI insights
            ai_search_queries = self.enhance_search_with_ai(ai_analysis, user_preferences)
            concept_queries = playlist_concept.get('search_queries', [])
            
            all_queries = ai_search_queries + concept_queries
            logger.info(f"Generated {len(all_queries)} AI-enhanced search queries")
            
            # Search for candidate tracks
            logger.info("Searching for candidate tracks...")
            candidate_tracks = self.search_tracks_advanced(all_queries, limit=15)
            
            if not candidate_tracks:
                logger.error("No candidate tracks found")
                return None
            
            logger.info(f"Found {len(candidate_tracks)} candidate tracks")
            
            # Score tracks with AI insights
            scored_tracks = self.score_tracks_with_ai_insights(candidate_tracks, ai_analysis, user_preferences)
            
            # Remove duplicates
            user_track_lists = [top_tracks, recently_played]
            unique_tracks = self.remove_duplicates_and_user_tracks(scored_tracks, user_track_lists)
            
            logger.info(f"After filtering: {len(unique_tracks)} unique tracks")
            
            # Select top tracks
            selected_tracks = unique_tracks[:playlist_size]
            
            if len(selected_tracks) < playlist_size // 2:
                logger.warning(f"Only found {len(selected_tracks)} tracks, less than expected")
            
            track_uris = [track_data['track']['uri'] for track_data in selected_tracks]
            
            # Create AI-generated playlist name and description
            raw_playlist_name = playlist_concept.get('playlist_name', f"AI Discovery - {datetime.now().strftime('%Y-%m-%d')}")
            
            # Clean playlist name
            playlist_name = self.clean_playlist_name(raw_playlist_name)
            
            # Enhanced description with AI insights
            primary_genres = ', '.join(ai_analysis.get('primary_genres', [])[:3])
            description = f"AI-curated playlist. Genres: {primary_genres}. Mood: {playlist_concept.get('target_mood', 'Balanced')}. Generated {datetime.now().strftime('%Y-%m-%d')}"
            
            # Ensure description is within Spotify's limits
            if len(description) > 300:
                description = description[:297] + "..."
            
            playlist = self.create_playlist(
                user_id=user['id'],
                playlist_name=playlist_name,
                track_uris=track_uris,
                description=description
            )
            
            if playlist:
                self.print_ai_playlist_summary(playlist, ai_analysis, playlist_concept, selected_tracks)
            
            return {
            "selected_tracks": selected_tracks,
            "playlist_concept": playlist_concept,
            "description": description
        }

            
        except Exception as e:
            logger.error(f"Error generating AI-enhanced playlist: {e}")
            return None
    def prepare_ai_playlist_preview(self, playlist_size=25, time_range='medium_term', 
                                mood=None, theme=None, occasion=None):
        try:
            logger.info("Preparing AI-enhanced playlist preview...")

            user = self.get_user_profile()
            if not user:
                logger.error("Could not get user profile")
                return None

            top_artists = self.get_top_artists(time_range=time_range)
            top_tracks = self.get_top_tracks(time_range=time_range)
            recently_played = self.get_recently_played()

            if not top_artists and not top_tracks:
                logger.error("Not enough data for preview")
                return None

            ai_analysis = self.analyze_music_with_ai(top_artists, top_tracks, recently_played)
            playlist_concept = self.generate_ai_playlist_concept(mood, theme, occasion)

            user_preferences = {
                'artists': Counter([track['artists'][0]['name'] for track in top_tracks]),
                'genres': Counter()
            }

            ai_search_queries = self.enhance_search_with_ai(ai_analysis, user_preferences)
            concept_queries = playlist_concept.get('search_queries', [])
            all_queries = ai_search_queries + concept_queries

            candidate_tracks = self.search_tracks_advanced(all_queries, limit=15)
            scored_tracks = self.score_tracks_with_ai_insights(candidate_tracks, ai_analysis, user_preferences)
            user_track_lists = [top_tracks, recently_played]
            unique_tracks = self.remove_duplicates_and_user_tracks(scored_tracks, user_track_lists)

            selected_tracks = unique_tracks[:playlist_size]
            track_uris = [track_data['track']['uri'] for track_data in selected_tracks]

            raw_playlist_name = playlist_concept.get('playlist_name', f"AI Discovery - {datetime.now().strftime('%Y-%m-%d')}")
            playlist_name = self.clean_playlist_name(raw_playlist_name)
            primary_genres = ', '.join(ai_analysis.get('primary_genres', [])[:3])
            description = f"AI-curated playlist. Genres: {primary_genres}. Mood: {playlist_concept.get('target_mood', 'Balanced')}. Generated {datetime.now().strftime('%Y-%m-%d')}"
            if len(description) > 300:
                description = description[:297] + "..."

            return {
                "selected_tracks": selected_tracks,
                "playlist_concept": playlist_concept,
                "description": description,
                "playlist_name": playlist_name,
                "track_uris": track_uris,
                "user_id": user['id']
            }

        except Exception as e:
            logger.error(f"Error preparing AI-enhanced playlist preview: {e}")
            return None

    def print_ai_playlist_summary(self, playlist, ai_analysis, playlist_concept, selected_tracks):
        """Print detailed summary of the AI-generated playlist"""
        
        print(f"\n🤖 AI-Enhanced Playlist Created!")
        print(f"🎵 Playlist: {playlist['name']}")
        print(f"📊 Spotify URL: {playlist['external_urls']['spotify']}")
        print(f"🎵 Total tracks: {len(selected_tracks)}")
        
        print(f"\n🧠 AI Music Analysis:")
        print(f"  • Personality: {ai_analysis.get('music_personality', 'N/A')}")
        print(f"  • Primary Genres: {', '.join(ai_analysis.get('primary_genres', []))}")
        print(f"  • Mood Preferences: {', '.join(ai_analysis.get('mood_preferences', []))}")
        print(f"  • Discovery Suggestions: {', '.join(ai_analysis.get('discovery_suggestions', {}).get('similar_artists', []))}")
        print(f"  • Playlist Themes: {', '.join([theme['name'] for theme in ai_analysis.get('playlist_themes', [])])}")
        print(f"  • Creative Insights: {ai_analysis.get('creative_insights', 'N/A')}")
        print(f"  • Recommended Search Strategies: {', '.join(ai_analysis.get('recommended_search_strategies', []))}")
        print(f"\n🎨 Playlist Concept:")
        print(f"  • Name: {playlist_concept.get('playlist_name', 'N/A')}")
        print(f"  • Description: {playlist_concept.get('description', 'N/A')}")
        print(f"  • Target Mood: {playlist_concept.get('target_mood', 'N/A')}")
        print(f"  • Search Queries: {', '.join(playlist_concept.get('search_queries', []))}")

        print(f"  • Genre Focus: {', '.join(playlist_concept.get('genre_focus', []))}")
        print(f"  • Energy Level: {playlist_concept.get('energy_level', 'N/A')}")
        print(f"  • Creative Elements: {', '.join(playlist_concept.get('creative_elements', []))}")     
        print("\n🎶 Selected Tracks:")
        for i, track_data in enumerate(selected_tracks, 1):
            track = track_data['track']
            print(f"  {i}. {track['name']} by {', '.join([artist['name'] for artist in track['artists']])} (Popularity: {track.get('popularity', 'N/A')})")
        print("\n🎉 Enjoy your AI-curated playlist on Spotify!")
    def run(self, username=None):
        """
        Main method to run the AI-enhanced playlist generation process
        """
        # Authenticate user and get Spotify client
        self.sp = self.authenticate_user(username)
        
        if not self.sp:
            logger.error("Failed to authenticate user")
            return None
        
        # Generate AI-enhanced playlist
        return self.generate_ai_enhanced_playlist()
if __name__ == "__main__":
    generator = AIEnhancedSpotifyGenerator(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        gemini_api_key=gemini_api_key
    )
    
    # Run the generator with a test username
    playlist = generator.run(username="test_user")
    
    if playlist:
        print(f"AI-enhanced playlist created successfully: {playlist['name']}")
    else:
        print("Failed to create AI-enhanced playlist.")