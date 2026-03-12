import asyncio
import logging
import sys
from dotenv import load_dotenv

# Load environment logic
load_dotenv()

# Setup logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

async def main():
    from promaia.brain.core.youtube_ingester import YouTubeIngester
    
    print("Initializing YouTube Ingester...")
    ingester = YouTubeIngester()
    
    print("\n--- Testing Single Channel Fetch (@Scrypster) ---")
    channel_data = ingester.get_channel_id("@Scrypster")
    if not channel_data:
        print("Failed to resolve @Scrypster.")
        return
        
    print(f"Channel ID: {channel_data['id']}")
    latest_vid = ingester.get_latest_video(channel_data)
    
    if not latest_vid:
        print("Failed to get latest video.")
        return
        
    vid_id = latest_vid['snippet']['resourceId']['videoId']
    vid_title = latest_vid['snippet']['title']
    print(f"Latest Video: {vid_title} (ID: {vid_id})")
    
    print("\nFetching Transcript...")
    transcript = ingester.get_transcript(vid_id)
    if transcript:
        print(f"Transcript fetched successfully! (Length: {len(transcript)} chars)")
        print(f"Preview: {transcript[:200]}...\n")
        
        print("\nSummarizing with LLM...")
        summary = ingester.summarize_transcript(transcript, vid_title, "Steve Yegge")
        print("\n=== SUMMARY ===")
        print(summary)
        print("================\n")
        
        print("Verification complete! (Skipped writing to DB for this test)")
    else:
        print("Failed to fetch transcript. Video might not have closed captions.")

if __name__ == "__main__":
    asyncio.run(main())
