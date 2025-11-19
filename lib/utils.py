import hashlib
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import re
import datetime

def normalize_url_for_hashing(url: str) -> str:
    try:
        parsed = urlparse(url)
        
        # 1. Lowercase scheme and hostname
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        
        # 2. Remove fragment
        fragment = ''
        
        # 3. Remove tracking parameters
        tracking_params = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'fbclid', 'gclid', 'msclkid', 'mc_cid', 'mc_eid',
            '_ga', '_gl', 'ref', 'source'
        }
        
        # Parse and filter query parameters
        params = parse_qs(parsed.query, keep_blank_values=True)
        filtered_params = {k: v for k, v in params.items() if k not in tracking_params}
        
        # Sort parameters for consistency
        query = urlencode(sorted(filtered_params.items()), doseq=True)
        
        # 4. Remove trailing slash from path
        path = parsed.path
        if len(path) > 1 and path.endswith('/'):
            path = path[:-1]
        
        
        normalized = urlunparse((scheme, netloc, path, parsed.params, query, fragment))
        return normalized
        
    except Exception:
        return url.lower()

def generate_article_id(url: str) -> str:
    normalized = normalize_url_for_hashing(url)
    hash_object = hashlib.sha256(normalized.encode('utf-8'))
    return hash_object.hexdigest()[:16]  # First 16 characters


def sentence_segmenter(text: str):
    """Simple sentence segmentation using periods. Placeholder for more advanced logic."""
    # sentences = [sentence.strip() for sentence in text.split('.') if sentence.strip()]

    sentences = re.split(r'(?<=[.!?]) +', text)
    article = {

    }

    # Sentences
    # parent_article_id (Foreign_Key)
    # sentence_id
    # sentence_text
    # sentence_order
    # context_left
    # context_right
    # source_outlet
    # source_url
    # published_at
    # date
    # topic

    sentences = [ 
        
    ]
    count = 0
    for sentence in sentences:
        left_context = ""
        right_context = ""
        if count > 0 and count < len(sentences) - 1:
            left_context = sentences[count - 1]
            right_context = sentences[count + 1]
                
        new_sentence = {
            "parent_article_id": None,
            "sentence_id": None,
            "sentence_text": sentence,
            "sentence_order": count,
            "context_left": left_context,
            "context_right": right_context,
            "source_outlet": None,
            "source_url": None,
            "published_at": None,
            "date": None,
            "topic": None,
            "ingested_at": datetime.datetime.now()
        }
        count += 1

        print(f"- {sentence}")
        sentences.append(new_sentence)
        
        
    return sentences