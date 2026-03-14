import os
import json
import logging
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

from promaia.config.youtube_channels import YOUTUBE_CHANNELS
from promaia.ai.nl_orchestrator import PromaiLLMAdapter
from promaia.storage.db_factory import get_db
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.core.memory_pipeline import capture_memory

logger = logging.getLogger(__name__)

class YouTubeIngester:
    """
    Ingests technical insights from trusted YouTube channels.
    Summarizes them via LLM and stores them in MuninnDB.
    """
    def __init__(self):
        # We need YOUTUBE_API_KEY for YouTube Data API (fallback to GOOGLE_API_KEY)
        self.api_key = os.getenv("YOUTUBE_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("YOUTUBE_API_KEY not found. YouTubeIngester cannot run.")
            
        self.youtube = build('youtube', 'v3', developerKey=self.api_key) if self.api_key else None
        self.llm = PromaiLLMAdapter()
        self.db = get_db()
        self.vector_mgr = VectorDBManager()

    def get_channel_id(self, handle: str) -> str:
        """Resolve a handle (e.g., @steveyegge) to a Channel ID."""
        # Try forHandle first
        try:
            req = self.youtube.channels().list(forHandle=handle, part="id,contentDetails")
            res = req.execute()
            if "items" in res and len(res["items"]) > 0:
                return res["items"][0]
        except Exception as e:
            logger.debug(f"forHandle failed for {handle}: {e}")

        # Fallback to search if forHandle isn't supported or fails
        clean_handle = handle.lstrip("@")
        req = self.youtube.search().list(q=clean_handle, type="channel", part="id,snippet", maxResults=1)
        res = req.execute()
        if "items" in res and len(res["items"]) > 0:
            item = res["items"][0]
            # Need to get contentDetails as well
            channel_id = item["id"]["channelId"]
            req_det = self.youtube.channels().list(id=channel_id, part="id,contentDetails")
            res_det = req_det.execute()
            if "items" in res_det and len(res_det["items"]) > 0:
                return res_det["items"][0]
                
        return None

    def get_latest_video_id(self, channel_data: dict, channel_id: str) -> dict:
        """Get the most recent video from a channel's uploads playlist."""
        try:
            uploads_id = channel_data["contentDetails"]["relatedPlaylists"]["uploads"]
            req = self.youtube.playlistItems().list(
                playlistId=uploads_id,
                part="snippet",
                maxResults=1
            )
            res = req.execute()
            if "items" in res and len(res["items"]) > 0:
                snippet = res["items"][0].get("snippet", {})
                return {
                    "videoId": snippet.get("resourceId", {}).get("videoId"),
                    "title": snippet.get("title", "Unknown Title"),
                    "publishedAt": snippet.get("publishedAt", "Unknown Date")
                }
        except Exception as e:
            logger.debug(f"Failed to get latest video for channel via playlist: {e}")

        # Fallback to search if playlist fails
        try:
            req = self.youtube.search().list(
                channelId=channel_id,
                order="date",
                part="snippet",
                type="video",
                maxResults=1
            )
            res = req.execute()
            if "items" in res and len(res["items"]) > 0:
                snippet = res["items"][0].get("snippet", {})
                return {
                    "videoId": res["items"][0]["id"]["videoId"],
                    "title": snippet.get("title", "Unknown Title"),
                    "publishedAt": snippet.get("publishedAt", "Unknown Date")
                }
        except Exception as e:
            logger.error(f"Failed to search for latest video: {e}")
        return None

    def _get_thumbnail_url(self, video_id: str) -> str:
        """Get the best available thumbnail URL for a video."""
        # YouTube provides thumbnail URLs in a predictable format
        # Try maxresdefault first, then fall back to lower res
        for quality in ['maxresdefault', 'hqdefault', 'mqdefault', 'default']:
            url = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
            try:
                resp = requests.head(url, timeout=5)
                if resp.status_code == 200:
                    return url
            except:
                continue
        return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

    def _download_thumbnail(self, video_id: str) -> Optional[str]:
        """Download the best thumbnail for a video."""
        try:
            save_dir = os.path.join(os.getcwd(), 'data', 'multimodal_assets', 'youtube')
            os.makedirs(save_dir, exist_ok=True)

            url = self._get_thumbnail_url(video_id)
            file_path = os.path.join(save_dir, f"{video_id}_thumb.jpg")

            response = requests.get(url, timeout=15)
            response.raise_for_status()

            with open(file_path, 'wb') as f:
                f.write(response.content)

            logger.info(f"Downloaded thumbnail for {video_id}: {file_path}")
            return file_path
        except Exception as e:
            logger.warning(f"Failed to download thumbnail for {video_id}: {e}")
            return None

    def get_transcript(self, video_id: str) -> str:
        """Fetch the transcript text for a video."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)
            
            try:
                # Try manually created first
                transcript = transcript_list.find_manually_created_transcript(['en'])
            except:
                # Fallback to generated
                transcript = transcript_list.find_generated_transcript(['en'])
                
            formatter = TextFormatter()
            return formatter.format_transcript(transcript.fetch())
        except Exception as e:
            logger.error(f"Failed to fetch transcript for {video_id}: {e}")
            return None

    def is_already_processed(self, video_id: str) -> bool:
        """Check if we've already ingested this video."""
        result = self.db.fetch_one(
            "SELECT id FROM memories WHERE source = 'youtube' AND source_id = %s",
            (video_id,)
        )
        return result is not None

    def summarize_transcript(self, transcript: str, video_title: str, creator_name: str) -> str:
        """Use LLM to extract key technical insights."""
        prompt = f"""
You are an expert technical analyst analyzing YouTube videos for a principal engineer.
The creator is "{creator_name}" and the video title is "{video_title}".

I will provide the raw transcript of the video. Your goal is to extract ONLY the high-signal, actionable intelligence:
- New AI framework or model announcements
- Architectural insights or coding techniques discussed
- Projects the creator is working on
- Specific tools, libraries, or methodologies recommended
- Opinions or predictions about the industry (if they are substantive)

Ignore filler, ads, basic introductory material, and generic advice.
Format your output as a concise, dense set of notes that will be saved as a cognitive memory.
Write it in the third-person (e.g., "{creator_name} discussed...").

TRANSCRIPT:
{transcript[:30000]} # Cap to ~30k chars to be safe with context windows, though Gemini can handle more
"""
        response = self.llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    async def run_sync(self):
        """Run the ingestion pipeline for all configured channels."""
        if not self.youtube:
            logger.error("Skipping YouTube ingestion (no API key).")
            return []

        ingested = []
        for channel_conf in YOUTUBE_CHANNELS:
            creator_name = channel_conf["name"]
            handle = channel_conf["handle"]
            
            logger.info(f"Checking YouTube for {creator_name} ({handle})...")
            
            # 1. Get Channel Data
            channel_data = self.get_channel_id(handle)
            if not channel_data:
                logger.warning(f"Could not resolve channel for {handle}")
                continue
                
            # 2. Get Latest Video
            channel_id = channel_data["id"] if isinstance(channel_data, dict) and "id" in channel_data else None
            if not channel_id:
                logger.error(f"Could not extract channelId from channel_data for {handle}")
                continue

            latest_video_info = self.get_latest_video_id(channel_data, channel_id)
            if not latest_video_info:
                logger.warning(f"Could not find any videos for {handle}")
                continue
                
            video_id = latest_video_info.get("videoId")
            video_title = latest_video_info.get("title", "Unknown Title")
            published_at = latest_video_info.get("publishedAt", "Unknown Date")
            
            if not video_id:
                logger.warning(f"Extracted video info missing videoId for {handle}")
                continue
                
            # 3. Check if processed
            if self.is_already_processed(video_id):
                logger.debug(f"Already processed {video_id} for {creator_name}")
                continue
                
            logger.info(f"New video found for {creator_name}: {video_title} ({video_id})")
            
            # 4. Get Transcript
            transcript = self.get_transcript(video_id)
            if not transcript:
                logger.warning(f"No transcript available for {video_id}")
                continue
                
            # 5. Summarize
            summary = self.summarize_transcript(transcript, video_title, creator_name)
            
            # 6. Prepend metadata block
            full_content = f"Source: YouTube Channel '{creator_name}'\nVideo Title: {video_title}\nVideo Date: {published_at}\nVideo ID: {video_id}\n\n{summary}"
            
            # 7. Download thumbnail
            thumb_path = self._download_thumbnail(video_id)
            image_paths = [thumb_path] if thumb_path else None
            
            # 8. Capture Memory (with thumbnail if available)
            try:
                await capture_memory(
                    db=self.db,
                    vector_mgr=self.vector_mgr,
                    content=full_content,
                    session_id=video_id,
                    domain_name="tech_radar",
                    source="youtube",
                    confidence=0.9,
                    image_paths=image_paths
                )
                logger.info(f"Successfully ingested video: {video_id} (thumbnail: {'yes' if thumb_path else 'no'})")
                ingested.append({"creator": creator_name, "title": video_title, "id": video_id})
            except Exception as e:
                logger.error(f"Failed to capture memory for {video_id}: {e}")
                
        return ingested
