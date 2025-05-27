import os
from flask import current_app
from flask_socketio import emit, join_room
from flask_login import current_user
import json
import uuid
import os
from datetime import datetime

from . import socketio, db
from .models import User, Video, Analysis, AnalysisVideo
from .youtube_service import YouTubeService
from .gemini_service import GeminiService
from . import cache  # Added for Flask-Caching
from googleapiclient.errors import HttpError  # Added for YouTube API error handling

def register_socket_events():
    """Register all WebSocket event handlers"""
    # This function will be called during app initialization
    pass

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room(current_user.id)
        emit('status', {'message': 'Connected to server'})
    else:
        return False  # Reject the connection

@socketio.on('search_videos')
def handle_search(data):
    """Handle search requests for YouTube videos with caching and robust error handling."""
    logger = getattr(current_app, 'logger', print) # Use print as fallback if logger not set up

    query = data.get('query', '')
    if not query or not isinstance(query, str):
        logger.warning(f"Invalid search query received: {query}")
        emit('error', {'message': 'Please provide a valid search term'})
        return

    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        logger.error("YouTube API key not found in environment variables")
        emit('error', {'message': 'YouTube API key not configured. Please contact support.'})
        return

    MAX_RESULTS = 20  # Requirement: Fetch up to 20 videos
    cache_key = f"youtube_search_{query.replace(' ', '_').lower()}_{MAX_RESULTS}"
    
    logger.info(f"Handling search for: '{query}', cache_key: {cache_key}")

    try:
        cached_videos = cache.get(cache_key)
        if cached_videos is not None:
            logger.info(f"Cache hit for '{query}'. Returning {len(cached_videos)} cached videos.")
            emit('search_results', {'videos': cached_videos})
            return

        logger.info(f"Cache miss for '{query}'. Fetching from YouTube API.")
        yt_service = YouTubeService(api_key)
        videos = yt_service.search_videos(query, max_results=MAX_RESULTS)
        
        if videos is None: 
             logger.warning(f"Search for '{query}' returned None from YouTubeService. Defaulting to empty list.")
             videos = [] 

        logger.info(f"Search for '{query}' found {len(videos)} videos. Caching results.")
        cache.set(cache_key, videos) 
        
        emit('search_results', {'videos': videos})

    except HttpError as e:
        error_message = "An error occurred with the YouTube API."
        error_reason = "unknown_api_error"
        try:
            error_content = json.loads(e.content.decode())
            error_details = error_content.get("error", {}).get("errors", [{}])[0]
            reason = error_details.get("reason", "unknown")
            message_detail = error_details.get("message", "No additional details provided.")
            
            error_reason = reason
            error_message = f"YouTube API Error ({reason}): {message_detail}"

            if reason == "quotaExceeded":
                error_message = "The YouTube API quota has been exceeded. Please try again later or contact support."
            elif reason == "keyInvalid":
                 error_message = "The YouTube API key is invalid. Please contact support."
            
            logger.error(f"YouTube API HttpError for query '{query}': {reason} - {message_detail}. Full error: {e.content.decode()}")
        except (json.JSONDecodeError, IndexError, KeyError, AttributeError) as parse_error:
            logger.error(f"YouTube API HttpError for query '{query}', but failed to parse error details: {str(e)}. Parse error: {str(parse_error)}")
        
        emit('error', {'message': error_message, 'reason': error_reason})
    
    except Exception as e:
        logger.error(f"Unexpected error during YouTube search for '{query}': {str(e)}", exc_info=True)
        emit('error', {'message': 'An unexpected error occurred while searching. Please try again.'})

@socketio.on('analyze_videos')
def handle_analyze(data):
    search_term = data.get('search_term')
    video_ids = data.get('video_ids', [])
    prompt = data.get('prompt')
    single_video_url = data.get('video_url')
    # Conversation tracking
    conversation_id = data.get('conversation_id')
    is_new_conversation = data.get('is_new_conversation', False)
    
    if not prompt:
        emit('error', {'message': 'Prompt is required'})
        return
    
    yt_service = YouTubeService(os.getenv('YOUTUBE_API_KEY'))
    
    # Case 1: Single video analysis
    if single_video_url:
        video_id = yt_service.get_video_id_from_url(single_video_url)
        if not video_id:
            emit('error', {'message': 'Invalid video URL'})
            return
            
        video_data = yt_service.get_video_by_id(video_id)
        if not video_data:
            emit('error', {'message': 'Video not found'})
            return
            
        video = Video.query.filter_by(video_id=video_id).first()
        if not video:
            video = Video(
                video_id=video_id,
                title=video_data['title'],
                url=video_data['url'],
                view_count=video_data.get('view_count', 0)
            )
            db.session.add(video)
            db.session.commit()
        
        # Get transcript
        transcript = yt_service.get_transcript(video.url)
        if not transcript:
            emit('error', {'message': 'Transcript not available for this video'})
            return
            
        video.transcript = transcript
        db.session.commit()
        
        # Create analysis with conversation support
        if is_new_conversation or not conversation_id:
            # Start a new conversation
            conversation_id = str(uuid.uuid4())
            is_conversation = True
            messages = json.dumps([{
                'role': 'user',
                'content': prompt,
                'timestamp': datetime.utcnow().isoformat()
            }])
        else:
            # Continue existing conversation
            # Find the previous analysis in this conversation
            prev_analysis = Analysis.query.filter_by(conversation_id=conversation_id).order_by(Analysis.created_at.desc()).first()
            is_conversation = True
            
            # Get existing messages and add the new one
            if prev_analysis and prev_analysis.messages:
                messages_list = json.loads(prev_analysis.messages)
                messages_list.append({
                    'role': 'user',
                    'content': prompt,
                    'timestamp': datetime.utcnow().isoformat()
                })
                messages = json.dumps(messages_list)
            else:
                # Fallback if something goes wrong with the previous messages
                messages = json.dumps([{
                    'role': 'user',
                    'content': prompt,
                    'timestamp': datetime.utcnow().isoformat()
                }])

        analysis = Analysis(
            user_id=current_user.id,
            search_term=None,
            prompt=prompt,
            conversation_id=conversation_id,
            is_conversation=is_conversation,
            messages=messages
        )
        db.session.add(analysis)
        db.session.commit()
        
        # Link video to analysis
        analysis_video = AnalysisVideo(
            analysis_id=analysis.id,
            video_id=video.id
        )
        db.session.add(analysis_video)
        db.session.commit()
        
        # Perform analysis
        gemini_service = GeminiService(current_user.gemini_api_key)
        video_with_transcript = {
            'title': video.title,
            'url': video.url,
            'transcript': video.transcript
        }
        
        emit('analysis_started', {'message': 'Analysis started'})
        
        # Stream analysis chunks
        chunks = []
        for chunk in gemini_service.stream_analysis(prompt, [video_with_transcript]):
            chunks.append(chunk)
            emit('analysis_chunk', {'chunk': chunk})
        
        # Save complete analysis
        result = ''.join(chunks)
        analysis.result = result
        
        # Update the messages with the assistant's response
        if analysis.messages:
            messages_list = json.loads(analysis.messages)
            messages_list.append({
                'role': 'assistant',
                'content': result,
                'timestamp': datetime.utcnow().isoformat()
            })
            analysis.messages = json.dumps(messages_list)
        
        db.session.commit()
        
        emit('analysis_complete', {'analysis_id': analysis.id, 'conversation_id': conversation_id})
        
    # Case 2: Multiple videos based on search
    elif search_term:
        # Search videos if no specific video_ids provided
        if not video_ids:
            videos_data = yt_service.search_videos(search_term)
            video_ids = [v['video_id'] for v in videos_data]
        
        # Retrieve videos from database or create them
        videos = []
        for video_id in video_ids:
            video = Video.query.filter_by(video_id=video_id).first()
            if not video:
                video_data = yt_service.get_video_by_id(video_id)
                if video_data:
                    video = Video(
                        video_id=video_id,
                        title=video_data['title'],
                        url=video_data['url'],
                        view_count=video_data.get('view_count', 0)
                    )
                    db.session.add(video)
                    db.session.commit()
            
            if video:
                # Get transcript if not already saved
                if not video.transcript:
                    transcript = yt_service.get_transcript(video.url)
                    if transcript:
                        video.transcript = transcript
                        db.session.commit()
                
                if video.transcript:
                    videos.append(video)
        
        if not videos:
            emit('error', {'message': 'No videos with transcripts found'})
            return
        
        # Create analysis with conversation support
        if is_new_conversation or not conversation_id:
            # Start a new conversation
            conversation_id = str(uuid.uuid4())
            is_conversation = True
            messages = json.dumps([{
                'role': 'user',
                'content': prompt,
                'timestamp': datetime.utcnow().isoformat()
            }])
        else:
            # Continue existing conversation
            # Find the previous analysis in this conversation
            prev_analysis = Analysis.query.filter_by(conversation_id=conversation_id).order_by(Analysis.created_at.desc()).first()
            is_conversation = True
            
            # Get existing messages and add the new one
            if prev_analysis and prev_analysis.messages:
                messages_list = json.loads(prev_analysis.messages)
                messages_list.append({
                    'role': 'user',
                    'content': prompt,
                    'timestamp': datetime.utcnow().isoformat()
                })
                messages = json.dumps(messages_list)
            else:
                # Fallback if something goes wrong with the previous messages
                messages = json.dumps([{
                    'role': 'user',
                    'content': prompt,
                    'timestamp': datetime.utcnow().isoformat()
                }])

        analysis = Analysis(
            user_id=current_user.id,
            search_term=search_term,
            prompt=prompt,
            conversation_id=conversation_id,
            is_conversation=is_conversation,
            messages=messages
        )
        db.session.add(analysis)
        db.session.commit()
        
        # Link videos to analysis
        for video in videos:
            analysis_video = AnalysisVideo(
                analysis_id=analysis.id,
                video_id=video.id
            )
            db.session.add(analysis_video)
        db.session.commit()
        
        # Prepare videos with transcripts for analysis
        videos_with_transcripts = [
            {
                'title': video.title,
                'url': video.url,
                'transcript': video.transcript
            }
            for video in videos if video.transcript
        ]
        
        # Perform analysis
        gemini_service = GeminiService(current_user.gemini_api_key)
        
        emit('analysis_started', {'message': 'Analysis started'})
        
        # Stream analysis chunks
        chunks = []
        for chunk in gemini_service.stream_analysis(prompt, videos_with_transcripts):
            chunks.append(chunk)
            emit('analysis_chunk', {'chunk': chunk})
        
        # Save complete analysis
        result = ''.join(chunks)
        analysis.result = result
        
        # Update the messages with the assistant's response
        if analysis.messages:
            messages_list = json.loads(analysis.messages)
            messages_list.append({
                'role': 'assistant',
                'content': result,
                'timestamp': datetime.utcnow().isoformat()
            })
            analysis.messages = json.dumps(messages_list)
        
        db.session.commit()
        
        emit('analysis_complete', {'analysis_id': analysis.id, 'conversation_id': conversation_id})
    
    else:
        emit('error', {'message': 'Either search_term or video_url is required'})
        return
