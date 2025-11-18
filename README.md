# Notarei-Backend
Backend Services for Notarei

## Overview

Flask-based REST API for news article ingestion, processing, and user management with Auth0 integration.

## News Sources

Reuters, Associated Press, BBC News, The Guardian, CNN, Al Jazeera English,
Bloomberg, The Washington Post, The Wall Street Journal, The New York Times,
SkyNews, Fox News.

## Installation Instructions

### Prerequisites

- Python 3.9 or higher
- MongoDB Atlas account or local MongoDB instance
- Auth0 account (for authentication)
- EventRegistry API key (for news ingestion)

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jeffreyft3/Notarei-Backend.git
   cd Notarei-Backend
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   
   Create a `.env.local` file in the root directory:
   ```bash
   # MongoDB
   MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
   MONGODB_DB=notarei
   
   # EventRegistry API
   NEWSAPI_KEY=your_eventregistry_api_key
   
   # Auth0
   AUTH0_DOMAIN=your-tenant.us.auth0.com
   AUTH0_AUDIENCE=https://api.notarei.com
   
   # Server
   PORT=4000
   ```

5. **Run the development server:**
   ```bash
   python3 backend.py
   ```
   
   The server will start on `http://localhost:4000`

### Production Deployment

For production, use Gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:4000 backend:app
```

## API Endpoints

### Public Endpoints
- `GET /news` - Fetch latest news articles from the last day
- `GET /articles` - Retrieve all articles from the database

### Protected Endpoints (Require Auth0 JWT)
- `GET /user/get` - Get current user profile and stats

### Admin Endpoints
- `GET /ingest/latest` - Ingest articles with custom parameters
- `GET /ingest/latest/us` - Ingest US articles from major news sources

## Project Structure

```
Notarei-Backend/
├── backend.py          # Main Flask application
├── auth.py             # Auth0 JWT verification
├── lib/
│   └── utils.py        # URL normalization and utilities
├── requirements.txt    # Python dependencies
├── .env.local          # Environment variables (not in git)
└── README.md           # This file
```

## Development

- Flask debug mode is enabled by default when running `python3 backend.py`
- CORS is configured to allow all origins (adjust in production)
- MongoDB collections: `rawArticles`, `sentences`, `cleanArticles`, `users`
