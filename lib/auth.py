import os
import requests
from jose import jwt
from flask import request, jsonify, g
from functools import wraps

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
AUTH0_ISSUER = f"https://{AUTH0_DOMAIN}/" if AUTH0_DOMAIN else None

_jwks_cache = None

def get_jwks():
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    if not AUTH0_DOMAIN:
        raise Exception("AUTH0_DOMAIN not set")
    jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    resp = requests.get(jwks_url)
    resp.raise_for_status()
    _jwks_cache = resp.json()["keys"]
    return _jwks_cache


def verify_jwt(token):
    if not AUTH0_DOMAIN or not AUTH0_AUDIENCE:
        raise Exception("AUTH0_DOMAIN or AUTH0_AUDIENCE not set")
    jwks = get_jwks()
    unverified_header = jwt.get_unverified_header(token)
    rsa_key = {}
    for key in jwks:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
    if not rsa_key:
        raise Exception("Unable to find appropriate key")
    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE,
            issuer=AUTH0_ISSUER
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("token is expired")
    except jwt.JWTClaimsError:
        raise Exception("incorrect claims, check audience and issuer")
    except Exception as e:
        raise Exception(f"Unable to parse token: {str(e)}")


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Allow CORS preflight requests to pass through without auth
        print("🔒 Authenticating request...", flush=True)
        auth_header = request.headers.get("Authorization", None)
        print(f"🔍 Authorization header: {auth_header}", flush=True)
        if request.method == 'OPTIONS':
            return ('', 204)
        if not auth_header:
            return jsonify({"error": "Authorization header missing"}), 401
        parts = auth_header.split()
        if parts[0].lower() != "bearer" or len(parts) != 2:
            return jsonify({"error": "Invalid Authorization header format"}), 401
        token = parts[1]
        print(f"🔑 Token (first 20 chars): {token[:20]}...", flush=True)
        try:
            payload = verify_jwt(token)
            g.user = payload
            print(f"✅ Auth successful for user: {payload.get('sub', 'unknown')}", flush=True)
            return f(*args, **kwargs)
        except Exception as e:
            print(f"❌ Auth failed: {str(e)}", flush=True)
            return jsonify({"error": "Unauthorized", "details": str(e)}), 401
    return decorated
