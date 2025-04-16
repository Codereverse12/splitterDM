from flask import redirect, session, request, current_app
from functools import wraps
import re
import hashlib
import hmac
from config import Config

def verify_signature(f):
    """
    Decorate routes to verify the request signature.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        signature = request.headers.get('X-Hub-Signature')
        
        if signature:
            # Ensure the signature format is valid
            signature_parts = signature.split("=")
            if len(signature_parts) != 2:
                return "Unrecognized signature format", 400
            
            signature_hash = signature_parts[1]
            
            # Compute the expected hash using the secret key and request body
            expected_hash = hmac.new(
                key=Config.appSecret.encode('utf-8'),  # Secret key as bytes
                msg=request.get_data(),  # Request body as bytes
                digestmod=hashlib.sha1  # Digest mode as SHA1
            ).hexdigest()

            # Use hmac.compare_digest to securely compare the signature hashes
            if not hmac.compare_digest(signature_hash, expected_hash):
                return "Couldn't validate the request signature.", 400

        else:
            print("\033[31mCouldn't find X-Hub-Signature header.\033[0m")
            return "Couldn't find required header", 400
        
        # Proceed to the original function
        return f(*args, **kwargs)
    
    return decorated_function

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/authorize")
        return f(*args, **kwargs)
    return decorated_function

def is_valid_input(text):
    return bool(re.fullmatch(r"\w+", text))

def instagram_username(url):
    """Extract Instagram username"""

    pattern =  r"(?:https?:\/\/(?:www\.)?instagram\.com\/|@)([a-zA-Z0-9_.]+)"

    match = re.search(pattern, url)
    if match:
        return match.group(1).lower()

def extract_reel_shortcode(text):
    pattern = r"https?:\/\/(www\.)?instagram\.com/reel/([A-Za-z0-9_-]+)\/?"

    match = re.search(pattern, text)
    return match.group(2) if match else None

def is_video_link(text):
    pattern = re.compile(
    r"""
    (https?:\/\/)?                                     # Optional scheme
    (www\.)?                                           # Optional www
    (                                                  # Start group of platforms
        (youtube\.com\/shorts\/[a-zA-Z0-9_-]{11})      # YouTube Shorts
        |                                              # OR
        (vm\.tiktok\.com\/[a-zA-Z0-9_-]+)            # TikTok links
        |
        (tiktok\.com\/@[\w.-]+\/video\/\d+)            # Full TikTok video links
    )
    (\/)?                                              # Optional trailing slash
    """, re.VERBOSE)
    mo = pattern.search(text)
    if mo is None:
        return None
    return mo.group()