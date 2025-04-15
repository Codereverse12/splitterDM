import os
from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env.

class Config:
    # Default countdown
    countdown = 20
    # Reels download directory
    reelsDirectory = "reels"
    # Gameplay video directory
    gameplayDirectory = "gameplays"
    # Output video directory
    outputDirectory= "outputs"
     
    # Gameplay thumbnail path
    thumbnailPath = "thumbnail"
    
    gameplayPerPage = 6
    outputPerPage = 8
    # Configure message broker
    celeryBrokerUrl = 'redis://localhost:6379/0'
    celeryResultBackend = 'redis://localhost:6379/0'
    # Application Config
    secretKey = os.environ["SECRET_KEY"]
    # Google oauth configs
    googleAuth = {
        "clientId": os.environ["GOOGLE_CLIENT_ID"],
        "clientSecret": os.environ["GOOGLE_CLIENT_SECRET"],
        "authUrl": "https://accounts.google.com/o/oauth2/auth",
        "tokenUrl": "https://accounts.google.com/o/oauth2/token",
        "userInfoUrl": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scopes": ["https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile", "openid"]
    }
    # Instagram config
    apiDomain = "https://graph.instagram.com"
    apiVersion = "v21.0"
    apiUrl = "https://graph.instagram.com" + "/" + "v22.0"
    
    # Instagram and Application information
    igId = os.environ["IG_ID"]
    igAccessToken = os.environ["IG_ACCESS_TOKEN"]
    appId = os.environ["IG_APP_ID"]
    appSecret = os.environ["IG_APP_SECRET"]
    verifyToken = os.environ["VERIFY_TOKEN"]
    
    # Database configurations
    dbName = os.environ["DB_DATABASE_NAME"]
    dbUser = os.environ["DB_USERNAME"]
    dbPass = os.environ["DB_PASSWORD"]
    dbHost = os.environ["DB_HOST"]
    dbPort = os.environ["DB_PORT"]
