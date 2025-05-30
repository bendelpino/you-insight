from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    jsonify,
    session,
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import time
import uuid
from .email_service import send_reset_email

from . import db, login_manager
from .models import User, Video, Analysis, AnalysisVideo
from .youtube_service import YouTubeService

# Create main blueprint
main = Blueprint("main", __name__)

# Rate limiting data
api_calls = {}
MAX_CALLS_PER_MINUTE = 10


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Custom decorators
def rate_limit(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = (
            current_user.get_id()
            if current_user.is_authenticated
            else request.remote_addr
        )
        current_time = int(time.time())

        # Initialize or clean up old calls
        if user_id not in api_calls:
            api_calls[user_id] = []
        api_calls[user_id] = [t for t in api_calls[user_id] if current_time - t < 60]

        # Check rate limit
        if len(api_calls[user_id]) >= MAX_CALLS_PER_MINUTE:
            return (
                jsonify(
                    {
                        "error": "Rate limit exceeded. Please wait before making more requests."
                    }
                ),
                429,
            )

        # Add current call
        api_calls[user_id].append(current_time)

        return f(*args, **kwargs)

    return decorated


# Routes
@main.route("/")
def index():
    return render_template("index.html")


@main.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")
        gemini_api_key = request.form.get("gemini_api_key")

        # Validate inputs
        if not email or not username or not password or not gemini_api_key:
            flash("All fields are required", "danger")
            return redirect(url_for("main.register"))

        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash("Email already registered", "danger")
            return redirect(url_for("main.register"))

        if User.query.filter_by(username=username).first():
            flash("Username already taken", "danger")
            return redirect(url_for("main.register"))

        # Create new user with UUID for Supabase RLS
        user = User(
            email=email,
            username=username,
            password_hash=generate_password_hash(password),
            gemini_api_key=gemini_api_key,
            user_id=str(uuid.uuid4()),  # Generate a UUID for Supabase RLS
        )
        db.session.add(user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html")


@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password", "danger")
            return redirect(url_for("main.login"))

        login_user(user)
        flash("Login successful!", "success")

        next_page = request.args.get("next")
        return redirect(next_page or url_for("main.chat"))

    return render_template("login.html")


@main.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        try:
            user = User.query.filter_by(email=email).first()

            if user:
                try:
                    # Generate a direct token (not using the database attributes if there's an issue)
                    import secrets
                    from datetime import datetime, timedelta

                    token = secrets.token_urlsafe(32)
                    expiry = datetime.utcnow() + timedelta(hours=1)

                    # Store the token in the session for now as a workaround
                    if "reset_tokens" not in session:
                        session["reset_tokens"] = {}

                    session["reset_tokens"][token] = {
                        "user_id": user.id,
                        "expiry": expiry.isoformat(),
                    }

                    # Create reset url with token
                    reset_url = url_for(
                        "main.reset_password", token=token, _external=True
                    )

                    # Send password reset email
                    email_sent = send_reset_email(user.email, reset_url)

                    if email_sent:
                        flash(
                            "A password reset link has been sent to your email address.",
                            "info",
                        )
                    else:
                        flash(
                            "There was an issue sending the password reset email. Please try again later.",
                            "danger",
                        )
                except Exception as e:
                    print(f"Error generating token: {str(e)}")
                    flash(
                        "An unexpected error occurred. Please try again later.",
                        "danger",
                    )
            else:
                # We don't want to reveal if an email exists in our database
                flash(
                    "A password reset link has been sent to your email address if it exists in our system.",
                    "info",
                )
        except Exception as e:
            print(f"Database error in forgot_password: {str(e)}")
            flash("An unexpected error occurred. Please try again later.", "danger")

        return redirect(url_for("main.login"))

    return render_template("forgot_password.html")


@main.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    # Check if token exists in the session
    reset_tokens = session.get("reset_tokens", {})
    token_data = reset_tokens.get(token)

    if not token_data:
        # Fallback to database token if session approach fails
        try:
            user = User.query.filter_by(reset_token=token).first()
            if not user or not user.verify_reset_token(token):
                flash("The password reset link is invalid or has expired.", "danger")
                return redirect(url_for("main.forgot_password"))
            user_id = user.id
        except Exception:
            flash("The password reset link is invalid or has expired.", "danger")
            return redirect(url_for("main.forgot_password"))
    else:
        # Use the session token
        from datetime import datetime

        expiry = datetime.fromisoformat(token_data["expiry"])
        if expiry < datetime.utcnow():
            # Token has expired
            flash("The password reset link has expired.", "danger")
            # Remove expired token
            del reset_tokens[token]
            session["reset_tokens"] = reset_tokens
            return redirect(url_for("main.forgot_password"))
        user_id = token_data["user_id"]

    # Get the user
    try:
        user = User.query.get(user_id)
        if not user:
            flash("User account not found.", "danger")
            return redirect(url_for("main.forgot_password"))
    except Exception as e:
        print(f"Error retrieving user in reset_password: {str(e)}")
        flash("An unexpected error occurred. Please try again later.", "danger")
        return redirect(url_for("main.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("reset_password.html", token=token)

        try:
            # Update the user's password
            user.password_hash = generate_password_hash(password)

            # Try to clear the token (database approach)
            try:
                if hasattr(user, "reset_token"):
                    user.reset_token = None
                if hasattr(user, "reset_token_expiry"):
                    user.reset_token_expiry = None
            except Exception:
                pass  # Ignore if this fails

            db.session.commit()

            # Clear the session token
            if token in reset_tokens:
                del reset_tokens[token]
                session["reset_tokens"] = reset_tokens

            flash(
                "Your password has been updated successfully. You can now log in with your new password.",
                "success",
            )
            return redirect(url_for("main.login"))
        except Exception as e:
            print(f"Error updating password: {str(e)}")
            db.session.rollback()
            flash(
                "There was an error updating your password. Please try again.", "danger"
            )

    return render_template("reset_password.html", token=token)


@main.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


@main.route("/chat")
@login_required
def chat():
    # Get conversation_id from URL parameters if present
    conversation_id = request.args.get("conversation_id")
    return render_template("chat.html", conversation_id=conversation_id)


@main.route("/history")
@login_required
def history():
    # Get all analyses for the current user
    all_analyses = (
        Analysis.query.filter_by(user_id=current_user.id)
        .order_by(Analysis.created_at.desc())
        .all()
    )

    # Dict to store latest conversation entry by conversation_id
    latest_conversations = {}
    regular_analyses = []

    # Group analyses by conversation_id
    for analysis in all_analyses:
        if analysis.is_conversation and analysis.conversation_id:
            # If this conversation hasn't been added yet, add it
            if analysis.conversation_id not in latest_conversations:
                latest_conversations[analysis.conversation_id] = analysis
        else:
            # Regular analyses (non-conversation) go directly to the list
            regular_analyses.append(analysis)

    # Combine the latest conversation entries with regular analyses
    analyses = list(latest_conversations.values()) + regular_analyses

    # Sort by created_at desc
    analyses.sort(key=lambda x: x.created_at, reverse=True)

    return render_template("history.html", analyses=analyses)


@main.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        gemini_api_key = request.form.get("gemini_api_key")
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")

        # Update API key if provided
        if gemini_api_key:
            current_user.gemini_api_key = gemini_api_key

        # Update password if provided
        if current_password and new_password:
            if check_password_hash(current_user.password_hash, current_password):
                current_user.password_hash = generate_password_hash(new_password)
                flash("Password updated", "success")
            else:
                flash("Current password is incorrect", "danger")
                return redirect(url_for("main.profile"))

        db.session.commit()
        flash("Profile updated successfully", "success")
        return redirect(url_for("main.profile"))

    return render_template("profile.html")


# API endpoints
@main.route("/api/search", methods=["POST"])
@login_required
@rate_limit
def search_videos():
    data = request.get_json()
    query = data.get("query")
    max_results = data.get("max_results", 10)

    if not query:
        return jsonify({"error": "Query is required"}), 400

    yt_service = YouTubeService(os.getenv("YOUTUBE_API_KEY"))
    videos = yt_service.search_videos(query, max_results)

    return jsonify({"videos": videos})


@main.route("/api/video/<video_id>", methods=["GET"])
@login_required
@rate_limit
def get_video(video_id):
    yt_service = YouTubeService(os.getenv("YOUTUBE_API_KEY"))
    video = yt_service.get_video_by_id(video_id)

    if not video:
        return jsonify({"error": "Video not found"}), 404

    return jsonify({"video": video})


@main.route("/api/transcript", methods=["POST"])
@login_required
@rate_limit
def get_transcript():
    data = request.get_json()
    video_url = data.get("video_url")

    if not video_url:
        return jsonify({"error": "Video URL is required"}), 400

    yt_service = YouTubeService(os.getenv("YOUTUBE_API_KEY"))
    transcript = yt_service.get_transcript(video_url)

    if not transcript:
        return jsonify({"error": "Transcript not available"}), 404

    return jsonify({"transcript": transcript})


@main.route("/api/analysis/<int:analysis_id>", methods=["GET"])
@login_required
def get_analysis(analysis_id):
    analysis = Analysis.query.filter_by(id=analysis_id, user_id=current_user.id).first()

    # Make sure the analysis belongs to the current user
    if analysis.user_id != current_user.id:
        return jsonify({"error": "Not authorized to view this analysis"}), 403

    # Get all videos associated with this analysis
    videos = []
    for av in analysis.videos:
        if av.video:
            video = av.video
            videos.append(
                {"video_id": video.video_id, "title": video.title, "url": video.url}
            )

    response = {
        "id": analysis.id,
        "prompt": analysis.prompt,
        "result": analysis.result,
        "videos": videos,
        "created_at": analysis.created_at.isoformat(),
    }

    return jsonify(response)


@main.route("/api/conversation/<conversation_id>")
@login_required
def get_conversation(conversation_id):
    # Get all analyses for this conversation ID, ordered by creation date
    analyses = (
        Analysis.query.filter_by(
            user_id=current_user.id, conversation_id=conversation_id
        )
        .order_by(Analysis.created_at.asc())
        .all()
    )

    if not analyses:
        return jsonify({"error": "Conversation not found"}), 404

    # Get videos from the most recent analysis
    videos = []
    latest_analysis = analyses[-1]  # Get the most recent analysis

    for av in latest_analysis.videos:
        if av.video:
            video = av.video
            videos.append(
                {
                    "video_id": video.video_id,
                    "title": video.title,
                    "url": video.url,
                    "single_video_url": video.url,
                }
            )

    # Extract conversation messages
    messages = []
    for analysis in analyses:
        if analysis.messages:
            try:
                import json

                analysis_messages = json.loads(analysis.messages)
                messages.extend(analysis_messages)
            except Exception as e:
                print(f"Error parsing messages for analysis {analysis.id}: {str(e)}")

    response = {
        "conversation_id": conversation_id,
        "messages": messages,
        "videos": videos,
    }

    return jsonify(response)
