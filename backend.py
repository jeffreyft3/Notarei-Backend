import json
import os
import hashlib
import certifi
from functools import wraps
from flask import Flask, request, jsonify, g
from pymongo import MongoClient
# from newsapi import QueryArticlesIter
from datetime import datetime, timedelta
from flask_cors import CORS
from dotenv import load_dotenv
from lib.utils import normalize_url_for_hashing, generate_article_id, sentence_segmenter
from eventregistry import EventRegistry, QueryArticlesIter
from lib.auth import requires_auth
# from auth import get_authenticated_user, userCollection
from bson import ObjectId

if os.path.exists(".env.local"):
    load_dotenv(dotenv_path=".env.local")
else:
    load_dotenv()  # fallback to .env
app = Flask(__name__)

# client = MongoClient(os.getenv("MONGODB_URI"))

frontend_url = os.getenv("FRONTEND_URL")
CORS(app,
     resources={r"/*": {
         "origins": [frontend_url],
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         "allow_headers": ["Authorization", "Content-Type"],
         "supports_credentials": True
     }})

print("Backend started", flush=True)
# cluster = 
mongoClient = MongoClient(os.getenv("MONGODB_URI"), tlsCAFile=certifi.where())
print("MongoDB connected:", mongoClient, flush=True)
db = mongoClient.Articles
pairingsCollection = db.pairings
annotationsCollection = db.annotations
cleanArticlesCollection = db.cleanArticles
rawArticlesCollection = db.rawArticles
sentencesCollection = db.sentences
# db = cluster[db_name] if cluster else None

sentenceCollection = db.sentences 
rawArticleCollection = db.rawArticles 
cleanArticleCollection = db.cleanArticles 
userCollection = db.users




# ------------------ User schema example ------------------
# {
#   "user_id": str,  # Auth0 sub
#   "email": str,
#   "name": str,
#   "role": str,  # enum: master, admin, moderator, annotator
#   "created_at": datetime,
#   "last_active_at": datetime,
#   "is_active": bool,
#   "completed_annotations": [annotation_id],
#   "completed_pairings": [pairing_id],
#   "current_pairings": [pairing_id],
#   "pairings_under_review": [pairing_id],
#   "annotations_count": int,
#   "average_session_length": float,
#   "time_per_annotation_avg": float
# }

@app.route("/user/get", methods=["POST", "GET", "OPTIONS"])
# @requires_auth
def get_or_create_user():
    """Handle user creation or retrieval."""
    if request.method == "OPTIONS":
        # Handle preflight requests
        return jsonify(success=True)

    # When @requires_auth is disabled for development, get data from request body
    if not hasattr(g, 'user'):
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        user_sub = data.get("auth0_id")
        user_email = data.get("email")
        user_name = data.get("name") # Or derive from email
    else:
        # When @requires_auth is enabled, use the validated JWT payload
        user_sub = g.user.get("sub")
        user_email = g.user.get("email")
        user_name = g.user.get("name")

    if not user_sub:
        return jsonify({"error": "No user_id (sub/auth0_id) provided."}), 400

    print("Fetching user with sub:", user_sub)
    user_doc = userCollection.find_one({"user_id": user_sub})
    print("Fetched user document:", user_doc)
    
    if not user_doc:
        # Determine role based on email domain
        default_role = "annotator"
        if user_email and "ft3.com" in user_email.lower():
            default_role = "admin"
            print(f"Auto-upgrading user to admin role (ft3.com email detected): {user_email}")
        
        # Create a new user record on first login
        user_doc = {
            "user_id": user_sub,
            "email": user_email,
            "name": user_name,
            "role": default_role,
            "created_at": datetime.now(),
            "last_active_at": datetime.now(),
            "is_active": True,
            "completed_annotations": [],
            "completed_pairings": [],
            "current_pairings": [],
            "pairings_under_review": [],
            "annotations_count": 0,
            "average_session_length": 0.0,
            "time_per_annotation_avg": 0.0
        }
        userCollection.insert_one(user_doc)
        print("Created new user document:", user_doc)
        
        # Convert ObjectId for the response
        if "_id" in user_doc:
            user_doc["_id"] = str(user_doc["_id"])
        return jsonify({"response": "New user created!", "user": user_doc}), 201
    else:
        # Update last_active_at on each request
        userCollection.update_one({"user_id": user_sub}, {"$set": {"last_active_at": datetime.now()}})

    if "_id" in user_doc:
        user_doc["_id"] = str(user_doc["_id"])

    return jsonify({"user": user_doc}), 200


@app.route("/user/list", methods=["POST"])
# @requires_auth
def list_all_users():
    """POST /user/list - Return all users (admin only).
    
    Requires authentication and admin role.
    """
    if userCollection is None:
        return jsonify({"error": "MongoDB not configured"}), 500
    
    try:
        # Get auth0_id from request body
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        user_sub = data.get("auth0_id")
        
        # # When @requires_auth is enabled, use JWT payload instead:
        # user_sub = g.user.get("sub")
        # if not user_sub:
        #     return jsonify({"error": "No user_id in JWT"}), 401
        
        if not user_sub:
            return jsonify({"error": "auth0_id is required"}), 400
        
        # Fetch the requesting user's document to check their role
        requesting_user = userCollection.find_one({"user_id": user_sub})
        
        if not requesting_user:
            return jsonify({"error": "User not found"}), 404
        
        # Verify the user has admin or master role
        user_role = requesting_user.get("role", "")
        if user_role not in ["admin", "master"]:
            return jsonify({"error": "Unauthorized. Admin role required."}), 403
        
        # Fetch all users
        users = list(userCollection.find())
        
        # Convert ObjectId to string for JSON serialization
        for user in users:
            if "_id" in user:
                user["_id"] = str(user["_id"])
        
        return jsonify({"users": users, "count": len(users)}), 200
        
    except Exception as e:
        print(f"Error listing users: {str(e)}")
        return jsonify({"error": "Failed to list users", "details": str(e)}), 500


# print("MongoDB connected:", bool(db), "DB:", db)


# er = EventRegistry(apiKey = )
# query = {
#   "$query": {
#     "$and": [
#       {
#         "locationUri": "http://en.wikipedia.org/wiki/United_States"
#       },
#       {
#         "lang": "eng"
#       }
#     ]
#   },
#   "$filter": {
#     "forceMaxDataTimeWindow": "31"
#   }
# }
# q = QueryArticlesIter.initWithComplexQuery(query)
# # change maxItems to get the number of results that you want
# for article in q.execQuery(er, maxItems=100):
#     print(article)

er = EventRegistry(apiKey=os.getenv("NEWSAPI_KEY"))


def build_query_with_sources(date_start: str,
                             date_end: str,
                             location_uri: str = "http://en.wikipedia.org/wiki/United_States",
                             lang: str = "eng",
                             sources: list[str] | None = None):
  """Build a complex EventRegistry query with optional $or source filters."""
  and_filters = [
    {"locationUri": location_uri},
    {"dateStart": date_start, "dateEnd": date_end, "lang": lang},
  ]
  if sources:
    and_filters.insert(1, {"$or": [{"sourceUri": s} for s in sources]})

  return {"$query": {"$and": and_filters}}


def _run_ingest(query: dict, max_items: int = 300):
  """Execute the query, upsert into rawArticles, and return a summary dict."""
  q_iter = QueryArticlesIter.initWithComplexQuery(query)

  fetched = 0
  inserted = 0
  updated = 0
  errors = []

  for article in q_iter.execQuery(er, maxItems=max_items):
    fetched += 1
    try:
      doc = dict(article)
      # Dedupe key: sha256(normalized URL) with preprocessing
      # - Remove fragments (after #)
      # - Remove tracking params (utm_*, fbclid, gclid, etc.)
      # - Normalize trailing slash
      key = None
      original_url = doc.get("url") or doc.get("link")
      if original_url:
        normalized_url = normalize_url_for_hashing(original_url)
        url_hash = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
        # Persist normalized URL and its hash for transparency/debugging
        doc["urlNormalized"] = normalized_url
        doc["urlHashSha256"] = url_hash
        key = url_hash
      else:
        # Fallbacks: prefer ER 'uri', else hash full doc for stability
        key = doc.get("uri")
        if not key:
          key = hashlib.sha256(json.dumps(doc, sort_keys=True).encode("utf-8")).hexdigest()

      # Store the dedupe key in 'uri' field used by upsert
      doc["uri"] = key
      doc["ingestedAt"] = datetime.now().isoformat()

      res = rawArticleCollection.update_one(
        {"uri": key},
        {"$set": doc, "$setOnInsert": {"createdAt": datetime.now().isoformat()}},
        upsert=True,
      )
      if res.upserted_id is not None:
        inserted += 1
      else:
        if res.matched_count:
          updated += 1
    except Exception as e:
      errors.append(str(e))

  return {
    "ok": True,
    "query": query,
    "counts": {"fetched": fetched, "inserted": inserted, "updated": updated},
    "errors": errors[:10],
  }


def _build_query_for_last_day(location_uri: str = "http://en.wikipedia.org/wiki/United_States", lang: str = "eng"):
  """Return a complex query dict for articles from the last day (UTC).

  Inputs: location_uri (str), lang (str)
  Output: dict suitable for QueryArticlesIter.initWithComplexQuery
  """
  today = datetime.now().date()
  yesterday = today - timedelta(days=1)
  return {
    "$query": {
      "$and": [
        {"locationUri": location_uri},
        {"dateStart": yesterday.isoformat(), "dateEnd": today.isoformat(), "lang": lang},
      ]
    }
  }

@app.route("/news", methods=["GET"])
def get_news_last_day():
  """GET /news

  Returns JSON list of articles from the last day (UTC). Uses NEWSAPI_KEY env var.
  Optional query params (currently supported): none. Future: locationUri, lang, maxItems
  """
  try:
    # use default US location and English language, can be extended to accept query params
    query = _build_query_for_last_day()
    q_iter = QueryArticlesIter.initWithComplexQuery(query)
    # choose a reasonable cap; clients can request less via a future param
    max_items = 100
    articles = []
    for article in q_iter.execQuery(er, maxItems=max_items):
      # EventRegistry returns rich objects; convert to JSON-serializable dicts
      # Keep the payload as-is if it's already a dict-like object
      try:
        cleanArticle = article.copy()
        # cleanArticle["body"] = json.loads(article["body"])
        articles.append(cleanArticle)
      except Exception:
        # fallback: convert to string
        articles.append({"raw": str(article)})

    return jsonify({"count": len(articles), "articles": articles}), 200
  except Exception as e:
    print("Error fetching news:", str(e))
    return jsonify({"error": "failed to fetch articles", "details": str(e)}), 500



@app.route("/ingest/latest", methods=["POST", "GET"])
def ingest_latest_articles():
  """Fetch latest articles using a source-filtered query and upsert to rawArticles.

  Query params (optional):
    - dateStart (YYYY-MM-DD) default: today-7d
    - dateEnd (YYYY-MM-DD) default: today
    - sources: comma-separated hostnames (default: reuters, apnews, nytimes, foxnews, washingtonpost)
    - locationUri: default US wiki URI
    - lang: default eng
    - maxItems: default 300
  """
  if not rawArticleCollection:
    return jsonify({"error": "MongoDB not configured (MONGODB_URI/MONGODB_DB)."}), 500
  if not os.getenv("NEWSAPI_KEY"):
    return jsonify({"error": "EventRegistry API key not configured (NEWSAPI_KEY)."}), 500

  today = datetime.now().date()
  date_start = request.args.get("dateStart", (today - timedelta(days=7)).isoformat())
  date_end = request.args.get("dateEnd", today.isoformat())
  location_uri = request.args.get("locationUri", "http://en.wikipedia.org/wiki/United_States")
  lang = request.args.get("lang", "eng")
  sources_param = request.args.get("sources")
  sources = [s.strip() for s in sources_param.split(",") if s.strip()] if sources_param else [
    "reuters.com", "apnews.com", "nytimes.com", "foxnews.com", "washingtonpost.com"
  ]
  try:
    max_items = int(request.args.get("maxItems", "300"))
  except ValueError:
    max_items = 300

  try:
    query = build_query_with_sources(date_start, date_end, location_uri, lang, sources)
    result = _run_ingest(query, max_items)
    return jsonify(result), 200
  except Exception as e:
    print("Error ingesting latest articles:", str(e))
    return jsonify({"error": "failed to ingest articles", "details": str(e)}), 500


@app.route("/ingest/latest/us", methods=["POST", "GET"])
def ingest_latest_us():
  """Ingest US articles from a fixed set of sources into rawArticles.

  Uses the query structure you provided (US location + OR list of sources),
  with a default date window of the last 1 day. Override with query params if needed.
  Params: dateStart, dateEnd, maxItems (optional)
  """
  if not rawArticleCollection:
    return jsonify({"error": "MongoDB not configured (MONGODB_URI/MONGODB_DB)."}), 500
  if not os.getenv("NEWSAPI_KEY"):
    return jsonify({"error": "EventRegistry API key not configured (NEWSAPI_KEY)."}), 500

  today = datetime.now().date()
  # Default to last 1 day for 'latest'
  default_start = (today - timedelta(days=1)).isoformat()
  default_end = today.isoformat()

  date_start = request.args.get("dateStart", default_start)
  date_end = request.args.get("dateEnd", default_end)
  try:
    max_items = int(request.args.get("maxItems", "100"))
  except ValueError:
    max_items = 100

  sources = [
    "reuters.com",
    "apnews.com",
    "nytimes.com",
    "foxnews.com",
    "washingtonpost.com",
  ]
  location_uri = "http://en.wikipedia.org/wiki/United_States"
  lang = "eng"

  try:
    query = build_query_with_sources(date_start, date_end, location_uri, lang, sources)
    result = _run_ingest(query, max_items)
    return jsonify(result), 200
  except Exception as e:
    print("Error ingesting US latest articles:", str(e))
    return jsonify({"error": "failed to ingest US latest", "details": str(e)}), 500

@app.route("/admin/newsapi/search", methods=["POST"])
def admin_newsapi_get():
  """ Admin endpoint to test complex queries against EventRegistry News API."""
  data = request.get_json()
  if not data:
    return jsonify({"error": "Request body must be JSON"}), 400
  fullQuery = {
    "query": {
    "$query": {
      "$and": [
        {
          "keyword": "Trump",
          "keywordLoc": "body"
        },
        {
          "keyword": "Trump",
          "keywordLoc": "title"
        },
        {
          "sourceUri": "reuters.com"
        },
        {
          "dateStart": "2025-11-13",
          "dateEnd": "2025-11-20",
          "lang": "eng"
        }
      ]

    }
    },
    "resultsType": "articles",
    "articlesSortBy": "date",
    "apiKey": os.getenv("NEWSAPI_KEY"),
  }
  query = {
    "$query": {
      "$and": [
        {
          "keyword": "Trump",
          "keywordLoc": "body"
        },
        {
          "keyword": "Trump",
          "keywordLoc": "title"
        },
        {
          "sourceUri": "reuters.com"
        },
        {
          "dateStart": "2025-11-13",
          "dateEnd": "2025-11-20",
          "lang": "eng"
        }
      ]

    }
  }
  """POST /newsapi/search - Execute custom EventRegistry query and return results.
  
  Request body:
    {
      "query": {
        "$query": {
          "$and": [
            {"keyword": "Trump", "keywordLoc": "body"},
            {"keyword": "Trump", "keywordLoc": "title"},
            {"sourceUri": "reuters.com"},
            {"dateStart": "2025-11-13", "dateEnd": "2025-11-20", "lang": "eng"}
          ]
        }
      },
      "maxItems": 100  // optional, default 100
    }
  
  Returns:
    {
      "articles": [...],
      "count": <number of articles returned>
    }
  """
  if not os.getenv("NEWSAPI_KEY"):
    return jsonify({"error": "EventRegistry API key not configured (NEWSAPI_KEY)."}), 500
  
  try:
    data = request.get_json()
    if not data:
      return jsonify({"error": "Request body must be JSON"}), 400
    
    query = data.get("query")
    if not query:
      return jsonify({"error": "query field is required"}), 400
    
    # Validate query structure
    if "$query" not in query or "$and" not in query["$query"]:
      return jsonify({"error": "Invalid query structure. Expected {\"$query\": {\"$and\": [...]}}"}), 400
    
    # Get maxItems from request or use default
    max_items = data.get("maxItems", 100)
    try:
      max_items = int(max_items)
      max_items = min(max(1, max_items), 500)  # Clamp between 1 and 500
    except (ValueError, TypeError):
      max_items = 100
    
    # Execute the query
    q_iter = QueryArticlesIter.initWithComplexQuery(query)
    articles = []
    
    for article in q_iter.execQuery(er, maxItems=max_items):
      try:
        # Convert to dict if needed
        article_dict = dict(article) if not isinstance(article, dict) else article
        articles.append(article_dict)
      except Exception as e:
        print(f"Error processing article: {str(e)}")
        continue
    
    print(f"NewsAPI search returned {len(articles)} articles")
    
    return jsonify({
      "articles": articles,
      "count": len(articles)
    }), 200
    
  except Exception as e:
    print(f"Error executing NewsAPI search: {str(e)}")
    return jsonify({"error": "Failed to execute search", "details": str(e)}), 500



@app.route("/newsapi/search", methods=["POST"])
def newsapi_search():
  """POST /newsapi/search - Execute custom EventRegistry query and return results.
  
  Request body:
    {
      "query": {
        "$query": {
          "$and": [
            {"keyword": "Trump", "keywordLoc": "body"},
            {"keyword": "Trump", "keywordLoc": "title"},
            {"sourceUri": "reuters.com"},
            {"dateStart": "2025-11-13", "dateEnd": "2025-11-20", "lang": "eng"}
          ]
        }
      },
      "maxItems": 100  // optional, default 100
    }
  
  Returns:
    {
      "articles": [...],
      "count": <number of articles returned>
    }
  """
  if not os.getenv("NEWSAPI_KEY"):
    return jsonify({"error": "EventRegistry API key not configured (NEWSAPI_KEY)."}), 500
  
  try:
    data = request.get_json()
    if not data:
      return jsonify({"error": "Request body must be JSON"}), 400
    
    query = data.get("query")
    if not query:
      return jsonify({"error": "query field is required"}), 400
    
    # Validate query structure
    if "$query" not in query or "$and" not in query["$query"]:
      return jsonify({"error": "Invalid query structure. Expected {\"$query\": {\"$and\": [...]}}"}), 400
    
    # Get maxItems from request or use default
    max_items = data.get("maxItems", 100)
    try:
      max_items = int(max_items)
      max_items = min(max(1, max_items), 500)  # Clamp between 1 and 500
    except (ValueError, TypeError):
      max_items = 100
    
    # Execute the query
    q_iter = QueryArticlesIter.initWithComplexQuery(query)
    articles = []
    
    for article in q_iter.execQuery(er, maxItems=max_items):
      try:
        # Convert to dict if needed
        article_dict = dict(article) if not isinstance(article, dict) else article
        articles.append(article_dict)
      except Exception as e:
        print(f"Error processing article: {str(e)}")
        continue
    
    print(f"NewsAPI search returned {len(articles)} articles")
    
    return jsonify({
      "articles": articles,
      "count": len(articles)
    }), 200
    
  except Exception as e:
    print(f"Error executing NewsAPI search: {str(e)}")
    return jsonify({"error": "Failed to execute search", "details": str(e)}), 500


@app.route("/articles", methods=["GET"])
def get_articles():
  """GET /articles - Return articles from the last day, evenly split across different sources."""
  if rawArticleCollection is None:
    return jsonify({"error": "MongoDB not configured (MONGODB_URI/MONGODB_DB)."}), 500
  try:
    # Calculate timestamp for 24 hours ago
    one_day_ago = datetime.now() - timedelta(days=1)
    one_day_ago_str = one_day_ago.isoformat()
    
    # Define target sources
    target_sources = ["apnews.com", "foxnews.com", "aljazeera.com"]
    
    # Calculate how many articles to take from each source
    articles_per_source = 50 // len(target_sources)  # Evenly split 50 articles
    remainder = 50 % len(target_sources)
    
    balanced_articles = []
    total_found = 0
    
    # Loop through each source and query MongoDB directly
    for idx, source in enumerate(target_sources):
      count = articles_per_source + (1 if idx < remainder else 0)
      
      # Build query for this specific source and date range
      source_query = {
        "source_uri": source,
        "$or": [
          {"date": {"$gte": one_day_ago_str}},
          {"dateTime": {"$gte": one_day_ago_str}},
          {"published_at": {"$gte": one_day_ago_str}}
        ]
      }
      
      # Fetch articles from this source
      source_articles = list(rawArticleCollection.find(source_query).sort("dateTime", -1).limit(count))
      print(f"Found {len(source_articles)} articles from {source}")
      
      balanced_articles.extend(source_articles)
      total_found += len(source_articles)
    
    # Convert ObjectId to string for JSON serialization
    for article in balanced_articles:
      if "_id" in article:
        article["_id"] = str(article["_id"])
    
    print(f"Returning {len(balanced_articles)} articles balanced across {len(target_sources)} sources")
    return jsonify({"articles": balanced_articles, "full_count": total_found}), 200
  except Exception as e:
    print("Error fetching articles:", str(e))
    return jsonify({"error": "failed to fetch articles", "details": str(e)}), 500


@app.route("/articles/<article_id>", methods=["GET"])
def get_article_by_id(article_id):
  """GET /articles/<article_id> - Return a specific article by its MongoDB ObjectId."""
  if rawArticleCollection is None:
    return jsonify({"error": "MongoDB not configured (MONGODB_URI/MONGODB_DB)."}), 500
  try:
    # Convert string ID to ObjectId
    article = rawArticleCollection.find_one({"_id": ObjectId(article_id)})
    
    if not article:
      return jsonify({"error": "Article not found"}), 404
    
    # Convert ObjectId to string for JSON serialization
    if "_id" in article:
      article["_id"] = str(article["_id"])
    
    return jsonify({"article": article}), 200
  except Exception as e:
    print(f"Error fetching article {article_id}:", str(e))
    return jsonify({"error": "Invalid article ID or fetch failed", "details": str(e)}), 400


@app.route("/articles/search", methods=["GET"])
def search_articles():
  """GET /articles/search - Search articles by keyword with pagination.
  
  Query params:
    - keyword: search term (required)
    - page: page number (default: 1)
    - limit: results per page (default: 20, max: 100)
  
  Returns:
    {
      "articles": [...],
      "pagination": {
        "page": 1,
        "limit": 20,
        "total": 150,
        "total_pages": 8,
        "has_next": true,
        "has_prev": false
      }
    }
  """
  if rawArticleCollection is None:
    return jsonify({"error": "MongoDB not configured"}), 500
  
  try:
    # Get query parameters
    keyword = request.args.get("keyword", "").strip()
    if not keyword:
      return jsonify({"error": "keyword parameter is required"}), 400
    
    # Pagination parameters
    try:
      page = max(1, int(request.args.get("page", "1")))
      limit = min(max(1, int(request.args.get("limit", "20"))), 100)
    except ValueError:
      page = 1
      limit = 20
    
    skip = (page - 1) * limit
    
    # Build search query (case-insensitive search in title and body)
    search_query = {
      "$or": [
        {"title": {"$regex": keyword, "$options": "i"}},
        {"body": {"$regex": keyword, "$options": "i"}},
        {"source.title": {"$regex": keyword, "$options": "i"}}
      ]
    }
    
    # Get total count for pagination
    total_count = rawArticleCollection.count_documents(search_query)
    total_pages = (total_count + limit - 1) // limit  # Ceiling division
    
    # Fetch paginated results
    articles = list(
      rawArticleCollection
        .find(search_query)
        .sort("dateTime", -1)
        .skip(skip)
        .limit(limit)
    )
    
    # Convert ObjectId to string for JSON serialization
    for article in articles:
      if "_id" in article:
        article["_id"] = str(article["_id"])
    
    print(f"Search for '{keyword}': found {total_count} articles, returning page {page}/{total_pages}")
    
    return jsonify({
      "articles": articles,
      "pagination": {
        "page": page,
        "limit": limit,
        "total": total_count,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
      }
    }), 200
    
  except Exception as e:
    print(f"Error searching articles: {str(e)}")
    return jsonify({"error": "Failed to search articles", "details": str(e)}), 500







############# Pairing routes #############

@app.route("/pairings/assign", methods=["POST"])
def assign_pairing():
  """POST /pairings/assign - Create a new pairing assignment.
  
  Request body:
    {
      "article_id": "art_abc123",
      "user1_id": "user_a1",
      "user2_id": "user_b2"
    }
  
  Returns:
    {
      "pairing": { ... newly created pairing document ... }
    }
  """
  if pairingsCollection is None:
    return jsonify({"error": "MongoDB not configured"}), 500
  
  try:
    data = request.get_json()
    if not data:
      return jsonify({"error": "Request body must be JSON"}), 400
    
    article_id = data.get("article_id")
    user1_id = data.get("user1_id")
    user2_id = data.get("user2_id")
    
    if not article_id or not user1_id or not user2_id:
      return jsonify({"error": "article_id, user1_id, and user2_id are required"}), 400
    
    # Generate a unique pairing_id (you can customize this format)
    import uuid
    pairing_id = f"pair_{uuid.uuid4().hex[:6]}"
    annotation_id_user1 = f"ann_{uuid.uuid4().hex[:6]}"
    annotation_id_user2 = f"ann_{uuid.uuid4().hex[:6]}"
    
    # Create new pairing document with empty fields
    new_pairing = {
      "pairing_id": pairing_id,
      "article_id": article_id,
      "created_at": datetime.now().isoformat(),
      "status": "assigned",  # Start with "assigned" status, not "completed"
      
      "user1_id": user1_id,
      "user2_id": user2_id,
      
      "user1_submitted_at": None,
      "user2_submitted_at": None,
      "combined_ready": False,
      "combined_at": None,
      "user1_annotation_id": annotation_id_user1,
      "user2_annotation_id": annotation_id_user2,
      
      "agreed_sentences": [],
      "disagreed_sentences": []
    }
    
    # Create initial annotation objects for both users
    new_annotation_user1 = {
      "annotation_id": annotation_id_user1,
      "article_id": article_id,
      "user_id": user1_id,
      "created_at": datetime.now().isoformat(),
      "submitted_at": None,
      "status": "not_started",
      "sentences": []
    }
    
    new_annotation_user2 = {
      "annotation_id": annotation_id_user2,
      "article_id": article_id,
      "user_id": user2_id,
      "created_at": datetime.now().isoformat(),
      "submitted_at": None,
      "status": "not_started",
      "sentences": []
    }
    
    # Insert into MongoDB
    result = pairingsCollection.insert_one(new_pairing)
    annotation_result1 = annotationsCollection.insert_one(new_annotation_user1)
    annotation_result2 = annotationsCollection.insert_one(new_annotation_user2)
    
    # Convert ObjectId to string for response
    new_pairing["_id"] = str(result.inserted_id)
    new_annotation_user1["_id"] = str(annotation_result1.inserted_id)
    new_annotation_user2["_id"] = str(annotation_result2.inserted_id)
    
    print(f"Created new pairing: {pairing_id} for article {article_id}")
    print(f"Created annotations: {annotation_id_user1}, {annotation_id_user2}")
    
    return jsonify({
      "pairing": new_pairing,
      "annotations": {
        "user1": new_annotation_user1,
        "user2": new_annotation_user2
      }
    }), 201
    
  except Exception as e:
    print(f"Error creating pairing: {str(e)}")
    return jsonify({"error": "Failed to create pairing", "details": str(e)}), 500





######### Annotations Routes #############


@app.route("/annotations/submit", methods=["POST"])
def submit_annotation():
  data = request.get_json()
  if not data:
    return jsonify({"error": "Request body must be JSON"}), 400

  annotation_id = data.get("annotation_id")
  sentences = data.get("sentences", [])

  result = annotationsCollection.find({"annotation_id": annotation_id}).update_one(
    {"$set": {sentences : sentences,
              "submitted_at": datetime.now().isoformat(),
              "status": "submitted"}}
  )
  if result.matched_count == 0:
    return jsonify({"error": "Annotation not found"}), 404
    
  return jsonify({"response": "Annotation submitted successfully."}), 201




############# User routes #############

# @app.route("/articles", methods=["GET"])
# def get_articles():
#   """GET /articles - Retrieve articles from rawArticles collection.

#   Query params:
#     - limit: max number of articles to return (default: 50, max: 500)
#     - skip: number of articles to skip for pagination (default: 0)
#     - sortBy: field to sort by (default: "ingestedAt")
#     - sortOrder: "asc" or "desc" (default: "desc")
#     - dateStart: filter by ingestedAt >= this ISO date (optional)
#     - dateEnd: filter by ingestedAt <= this ISO date (optional)
#     - source: filter by source.uri containing this string (optional)
  
#   Returns:
#     {
#       "articles": [...],
#       "count": <number of articles returned>,
#       "total": <total matching articles in DB>,
#       "limit": <applied limit>,
#       "skip": <applied skip>
#     }
#   """
#   if rawArticleCollection is None:
#     return jsonify({"error": "MongoDB not configured (MONGODB_URI/MONGODB_DB)."}), 500

#   try:
#     # Parse pagination params
#     try:
#       limit = min(int(request.args.get("limit", "50")), 500)
#       skip = max(int(request.args.get("skip", "0")), 0)
#     except ValueError:
#       limit = 50
#       skip = 0

#     # Parse sorting params
#     sort_by = request.args.get("sortBy", "ingestedAt")
#     sort_order = request.args.get("sortOrder", "desc")
#     sort_direction = -1 if sort_order == "desc" else 1

#     # Build filter query
#     filter_query = {}
    
#     # Date range filters
#     date_start = request.args.get("dateStart")
#     date_end = request.args.get("dateEnd")
#     if date_start or date_end:
#       filter_query["ingestedAt"] = {}
#       if date_start:
#         filter_query["ingestedAt"]["$gte"] = date_start
#       if date_end:
#         filter_query["ingestedAt"]["$lte"] = date_end

#     # Source filter
#     source_filter = request.args.get("source")
#     if source_filter:
#       filter_query["source.uri"] = {"$regex": source_filter, "$options": "i"}

#     # Execute query with pagination
#     cursor = rawArticleCollection.find(filter_query).sort(sort_by, sort_direction).skip(skip).limit(limit)
#     articles = list(cursor)
    
#     # Convert ObjectId to string for JSON serialization
#     for article in articles:
#       if "_id" in article:
#         article["_id"] = str(article["_id"])

#     # Get total count
#     total = rawArticleCollection.count_documents(filter_query)

#     return jsonify({
#       "articles": articles,
#       "count": len(articles),
#       "total": total,
#       "limit": limit,
#       "skip": skip,
#       "filter": filter_query
#     }), 200

#   except Exception as e:
#     print("Error fetching articles:", str(e))
#     return jsonify({"error": "failed to fetch articles", "details": str(e)}), 500


# Removed @app.after_request CORS handler to avoid conflicts with flask_cors
# The CORS configuration is handled by the CORS() initialization above


if __name__ == '__main__':
  # When run directly, start a debug server (development use only).
  app.run(host='0.0.0.0', port=int(os.getenv('PORT', 4000)), debug=True)