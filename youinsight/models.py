from flask_login import UserMixin
from datetime import datetime, timedelta
import secrets
import json
from sqlalchemy.dialects.postgresql import JSONB
from . import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), unique=True, nullable=True)  # Used for Supabase RLS
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)  # Increased from 128 to 255 for scrypt hashes
    gemini_api_key = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    analyses = db.relationship('Analysis', backref='user', lazy=True)
    
    def generate_reset_token(self):
        """Generate a secure token for password reset"""
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
        return self.reset_token
    
    def verify_reset_token(self, token):
        """Verify that the reset token is valid"""
        if self.reset_token != token:
            return False
        if self.reset_token_expiry < datetime.utcnow():
            return False
        return True
    
    def clear_reset_token(self):
        """Clear the reset token after it's used"""
        self.reset_token = None
        self.reset_token_expiry = None
    
    def __repr__(self):
        return f'<User {self.username}>'

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    view_count = db.Column(db.Integer, nullable=True)
    transcript = db.Column(db.Text, nullable=True)
    # Store complete YouTube API response as JSONB for efficient querying
    api_response = db.Column(JSONB, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    analyses = db.relationship('AnalysisVideo', backref='video', lazy=True)
    
    def __repr__(self):
        return f'<Video {self.title}>'
    
    def to_dict(self):
        data = {
            'id': self.id,
            'video_id': self.video_id,
            'title': self.title,
            'url': self.url,
            'view_count': self.view_count,
            'created_at': self.created_at.isoformat()
        }
        
        # Include API response if available
        if self.api_response:
            data['api_response'] = self.api_response
            
        return data

class Analysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    search_term = db.Column(db.String(100), nullable=True)
    prompt = db.Column(db.Text, nullable=False)
    # Store Gemini API result as JSONB for more efficient querying in PostgreSQL
    result = db.Column(db.Text, nullable=True)  # Keep as Text for backward compatibility
    result_json = db.Column(JSONB, nullable=True)  # For structured results
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    videos = db.relationship('AnalysisVideo', backref='analysis', lazy=True)
    # Conversation tracking
    conversation_id = db.Column(db.String(100), nullable=True)
    is_conversation = db.Column(db.Boolean, default=False)
    # Store messages as JSONB instead of Text for better JSON handling
    messages = db.Column(JSONB, nullable=True)  # JSON of conversation messages
    
    def __repr__(self):
        return f'<Analysis {self.id}>'
    
    def to_dict(self):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'search_term': self.search_term,
            'prompt': self.prompt,
            'result': self.result,
            'created_at': self.created_at.isoformat(),
            'videos': [av.video.to_dict() for av in self.videos],
            'is_conversation': self.is_conversation,
            'conversation_id': self.conversation_id
        }
        
        # Add structured result if available
        if self.result_json:
            data['result_json'] = self.result_json
        
        # Add messages if this is a conversation
        # With PostgreSQL JSONB, we don't need to parse the JSON string
        if self.is_conversation and self.messages:
            data['messages'] = self.messages
                
        return data

class AnalysisVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('analysis.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AnalysisVideo {self.id}>'
