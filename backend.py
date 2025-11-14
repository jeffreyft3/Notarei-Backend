import json
import os
from functools import wraps
from flask import Flask, request, jsonify, g
from pymongo import MongoClient
# from newsapi import QueryArticlesIter
from datetime import datetime, timedelta
from flask_cors import CORS
from dotenv import load_dotenv
from lib.utils import normalize_url_for_hashing, generate_article_id, sentence_segmenter
from eventregistry import EventRegistry, QueryArticlesIter
# from auth import get_authenticated_user, userCollection


load_dotenv(dotenv_path='.env.local')
app = Flask(__name__)
CORS(app)
# client = MongoClient(os.getenv("MONGODB_URI"))

# Checks for valid JWT and user in DB
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            auth_user = get_authenticated_user()
            print("Auth user:", auth_user)
            user = userCollection.find_one({"auth0_id": auth_user["sub"]})
            if not user:
                return jsonify({"error": "User not found"}), 404
            # Store user in Flask's `g` object for access in route
            g.user = user
            return f(*args, **kwargs)
        except Exception as e:
            print("❌ Auth failed:", str(e))
            return jsonify({"error": "Unauthorized", "details": str(e)}), 401
    return decorated


cluster = MongoClient(os.getenv("MONGODB_URI"))

sentenceCollection = db.sentences
rawArticleCollection = db.rawArticles
cleanArticleCollection = db.cleanArticles

print("MongoDB connected:", cluster)


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


def _build_query_for_last_day(location_uri: str = "http://en.wikipedia.org/wiki/United_States", lang: str = "eng"):
  """Return a complex query dict for articles from the last day (UTC).

  Inputs: location_uri (str), lang (str)
  Output: dict suitable for QueryArticlesIter.initWithComplexQuery
  """
  today = datetime.utcnow().date()
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


@app.route("/ingest/latest", methods=["POST"])
def ingest_latest_articles():
    """POST /ingest/latest

    Ingest latest articles from the last day into the system.
    Currently a stub; implementation depends on ingestion logic.
    """
    try:
        # Placeholder for ingestion logic
        # e.g., fetch articles, process them, store in DB, etc.
        return jsonify({"message": "Ingestion of latest articles not yet implemented."}), 200
    except Exception as e:
        print("Error ingesting latest articles:", str(e))
        return jsonify({"error": "failed to ingest articles", "details": str(e)}), 500





        # new_sentence = {
        #     "parent_article_id": None,
        #     "sentence_id": None,
        #     "text": sentence,
        #     "sentence_order": count,
        #     "start_offset": start_offset,
        #     "context_left": left_context,
        #     "context_right": right_context,
        #     "source_outlet": None,
        #     "source_url": None,
        #     "published_at": None,
        #     "date": None,
        #     "topic": None,
        #     "ingested_at": datetime.datetime.now()
        # }

    return sentences


if __name__ == '__main__':
  # When run directly, start a debug server (development use only).
  app.run(host='0.0.0.0', port=int(os.getenv('PORT', 4000)), debug=True)