import os
import re
import json
import logging
from typing import List, Dict, Optional, Any
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from . import cache

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YouTubeService:
    def __init__(self, api_key: str):
        """Initialize YouTube API service with the provided API key."""
        if not api_key:
            logger.error("YouTube API key is missing")
            raise ValueError("YouTube API key is required")
            
        self.api_key = api_key
        logger.info(f"Initializing YouTube service with API key: {api_key[:5]}...")
        
        try:
            self.youtube = build("youtube", "v3", developerKey=api_key)
            logger.info("YouTube API client successfully built")
        except Exception as e:
            logger.error(f"Failed to initialize YouTube API: {str(e)}")
            raise
            
    def test_api_key(self) -> bool:
        """Test if the API key is valid by making a simple request"""
        logger.info("Testing YouTube API key")
        try:
            # Make a minimal API request to test the key
            response = self.youtube.videos().list(part="snippet", id="dQw4w9WgXcQ").execute()
            logger.info("API key test successful")
            return True
        except Exception as e:
            logger.error(f"YouTube API key test failed: {str(e)}")
            return False
    
    def search_videos(self, search_term: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for YouTube videos based on the provided search term."""
        logger.info(f"Searching for '{search_term}', max results: {max_results}")
        
        try:
            # Step 1: Search for videos
            logger.info("Executing search request")
            search_response = self.youtube.search().list(
                q=search_term,
                part="id,snippet",
                maxResults=max_results,
                type="video"
            ).execute()
            
            logger.info(f"Found {len(search_response.get('items', []))} search results")
            
            # If no results, return empty list
            if not search_response.get("items"):
                logger.warning("No search results found")
                return []
            
            # Extract video IDs
            video_ids = []
            for item in search_response.get("items", []):
                if item.get("id", {}).get("videoId"):
                    video_ids.append(item["id"]["videoId"])
            
            if not video_ids:
                logger.warning("No valid video IDs found in search results")
                return []
                
            # Step 2: Get video details including statistics
            logger.info(f"Getting details for {len(video_ids)} videos")
            videos_response = self.youtube.videos().list(
                part="snippet,statistics",
                id=",".join(video_ids)
            ).execute()
            
            # Process videos and extract relevant information
            videos = []
            for video in videos_response.get("items", []):
                try:
                    # Extract data with fallbacks for missing fields
                    snippet = video.get("snippet", {})
                    statistics = video.get("statistics", {})
                    
                    # Handle missing thumbnails
                    thumbnails = snippet.get("thumbnails", {})
                    thumbnail_url = ""
                    for quality in ["high", "medium", "default"]:
                        if quality in thumbnails and "url" in thumbnails[quality]:
                            thumbnail_url = thumbnails[quality]["url"]
                            break
                    
                    # Get view count with fallback
                    try:
                        view_count = int(statistics.get("viewCount", 0))
                    except (ValueError, TypeError):
                        view_count = 0
                    
                    video_info = {
                        "video_id": video.get("id", ""),
                        "title": snippet.get("title", "Untitled Video"),
                        "url": f"https://www.youtube.com/watch?v={video.get('id', '')}",
                        "view_count": view_count,
                        "thumbnail_url": thumbnail_url,  # Renamed from 'thumbnail'
                        "channel_title": snippet.get("channelTitle", "Unknown Channel"),
                        "published_at": snippet.get("publishedAt", "")
                    }
                    videos.append(video_info)
                    
                except Exception as e:
                    logger.error(f"Error processing video data: {str(e)}")
                    # Continue processing other videos
                    continue
            
            logger.info(f"Successfully processed {len(videos)} videos")
            return videos
            
        except HttpError as e:
            logger.error(f"YouTube API HTTP error: {str(e)}")
            # Attempt to parse the error response
            try:
                error_content = json.loads(e.content.decode())
                error_details = error_content.get("error", {}).get("errors", [])
                if error_details:
                    logger.error(f"Error details: {error_details[0].get('reason')}: {error_details[0].get('message')}")
            except:
                pass
            raise  # Re-raise the HttpError
            
        except Exception as e:
            logger.error(f"Error searching videos: {str(e)}")
            return []
    
    @staticmethod
    def get_video_id_from_url(url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        patterns = [r"(?:v=|/)([0-9A-Za-z_-]{11}).*", r"youtu.be/([0-9A-Za-z_-]{11})"]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    @cache.memoize(timeout=86400)  # Cache transcripts for 24 hours
    def get_transcript(self, video_url: str) -> Optional[str]:
        """Get transcript for a YouTube video."""
        video_id = self.get_video_id_from_url(video_url)
        if not video_id:
            return None

        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            formatter = TextFormatter()
            return formatter.format_transcript(transcript)
        except Exception as e:
            print(f"Error getting transcript: {str(e)}")
            return None
    
    def get_video_by_id(self, video_id: str) -> Optional[Dict[str, str]]:
        """Get video details by video ID."""
        try:
            video_response = (
                self.youtube.videos()
                .list(part="snippet,statistics", id=video_id)
                .execute()
            )
            
            if not video_response["items"]:
                return None
                
            video = video_response["items"][0]
            
            # Handle potential missing statistics
            view_count = 0
            if "statistics" in video and "viewCount" in video["statistics"]:
                view_count = int(video["statistics"]["viewCount"])
                
            video_info = {
                "video_id": video["id"],
                "title": video["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={video['id']}",
                "view_count": view_count,
                "thumbnail": video["snippet"]["thumbnails"]["high"]["url"],
                "channel_title": video["snippet"]["channelTitle"],
                "published_at": video["snippet"]["publishedAt"]
            }
            
            return video_info
        except Exception as e:
            print(f"Error getting video by ID: {str(e)}")
            return None
