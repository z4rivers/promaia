import logging
import asyncio
from google.genai import types

logger = logging.getLogger(__name__)

async def handle(ft) -> types.FunctionResponse:
    if ft.name == "sync_youtube_context":
        logger.info("Triggering YouTube background sync...")
        try:
            from promaia.brain.core.youtube_ingester import YouTubeIngester
            
            async def run_ingestion():
                ingester = YouTubeIngester()
                await ingester.run_sync()
                
            # Run asynchronously so we don't block the voice bridge
            asyncio.create_task(run_ingestion())
            
            # Immediately pull the EXISTING cache to feed the agent now, but truncate to fit in WS payload bounds
            from promaia.storage.db_factory import get_db
            db = get_db()
            recent = db.fetch_all("SELECT content FROM memories WHERE source='youtube' ORDER BY created_at DESC LIMIT 5")
            
            summary_list = []
            for r in recent:
                text = r.get("content", "")
                if len(text) > 500:
                    text = text[:500] + "... [TRUNCATED FOR LENGTH. USE RECALL_MEMORY OR SEARCH_BRAIN IF YOU NEED THE FULL TRANSCRIPT]"
                summary_list.append(text)
            summaries = "\n\n".join(summary_list)
            
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={
                    "result": "youtube_sync_started_in_background",
                    "existing_cache": summaries
                }
            )
        except Exception as e:
            logger.error(f"Failed to start YouTube sync: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error", "error": str(e)}
            )

    elif ft.name == "query_youtube_transcript":
        logger.info(f"Triggering direct YouTube query for video {ft.args.get('video_id')}...")
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api.formatters import TextFormatter
            from google import genai
            import os

            video_id = ft.args.get("video_id")
            question = ft.args.get("question")
            
            # Fetch full transcript
            transcript_list = YouTubeTranscriptApi.list(video_id)
            try:
                transcript = transcript_list.find_manually_created_transcript(['en'])
            except:
                transcript = transcript_list.find_generated_transcript(['en'])
                
            formatter = TextFormatter()
            text_result = formatter.format_transcript(transcript.fetch())
            
            # Call Gemini on the backend to synthesize the 1-hour video down to a dense answer
            rag_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
            prompt = f"Transcript from YouTube video ({video_id}):\n\n{text_result[:80000]}\n\nAnalyze this transcript deeply. Answer the user's specific question or request: {question}\n\nProvide a very dense, direct, highly technical answer using exclusively the facts from the transcript. Make it concise enough to be spoken aloud (max 200 words). If the transcript doesn't answer it, explicitly state that."
            
            rag_response = rag_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "success", "answer": rag_response.text}
            )
        except Exception as e:
            logger.error(f"Failed to query transcript: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error", "error": str(e)}
            )
