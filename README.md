# YouInsight: YouTube Video Analysis Chatbot

A Flask-based web application that allows users to analyze YouTube videos using Google's Gemini API.

## Features

- Search for YouTube videos by keyword
- Analyze individual videos or collections of videos
- Custom analysis prompts
- Real-time communication via WebSockets
- User authentication system
- Caching for improved performance

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Create a `.env` file with your API keys:
   ```
   YOUTUBE_API_KEY=your_youtube_api_key
   SECRET_KEY=your_flask_secret_key
   ```

## Usage

1. Start the development server:
   ```
   python app.py
   ```
2. Open your browser and navigate to `http://localhost:5000`
3. Register an account, providing your own Gemini API key
4. Start interacting with the chatbot

## Deployment

This application can be deployed on platforms like:
- Heroku
- Render
- PythonAnywhere
- Any platform supporting Python web applications

## License

MIT
