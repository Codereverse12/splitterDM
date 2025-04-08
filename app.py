import os
from flask import Flask, render_template, request, url_for, session, redirect, flash, jsonify, send_from_directory, abort
from flask_session import Session
from config import Config
import secrets
import requests
from urllib.parse import urlencode
from my_db import query_db
import datetime
from helpers import login_required, verify_signature, is_valid_input, instagram_username
from config_celery import celery_init_app
from uuid import uuid4
import datetime
import graph_api
from receive import Receive
import redis 
import json
from graph_api import GraphApi
from video_processor import VideoProcessor

app = Flask(__name__)

# Setup Celery client
celery = celery_init_app(app)

# Setup redis 
redis_client = redis.Redis(host='127.0.0.1', port=6379, db=0)

app.config["SECRET_KEY"] = Config.secretKey

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dashboard")
@login_required
def dashboard():
    rows = query_db("SELECT * FROM video_configurations WHERE user_id = ?;", session["user_id"])
    if not rows:
        rows = []
    return render_template("dashboard.html", configs=rows)

@app.route("/default-config", methods=["POST"])
@login_required
def default_config():
    configId = request.form.get("config_id")
    state = request.form.get("state")
    query = """
        UPDATE 
            Users 
        SET 
            default_config_id = ? WHERE id = ? AND EXISTS (SELECT * FROM video_configurations WHERE user_id = ? AND id = ?);
    """
    new_config_id = configId if state == "set" else None
    is_updated = query_db(query, new_config_id,  session["user_id"], session["user_id"], configId)
    if is_updated:
        flash("Config successfully updated", "success")
    else:
        flash("Error setting default configuration", "danger")
    
    return redirect(url_for("dashboard"))

@app.route("/new-config", methods=["GET", "POST"])
@login_required
def new_config():
    """Create video configurations"""
    if request.method == "GET":
        accounts = query_db("SELECT * FROM ConnectedAccounts WHERE user_id = ?;", session["user_id"])
        return render_template("new_config.html", accounts=accounts or [])

    # Ensure the config name was submitted
    if not (request.form.get("configName") and is_valid_input(request.form["configName"])):
        flash("must provide a valid config name", "danger")
        return redirect(url_for("new_config"))
    
    # Check if config name exists
    config_name = request.form["configName"].lower().strip()
    rows = query_db("SELECT * FROM video_configurations WHERE config_name = ? AND user_id = ?;", config_name, session["user_id"])
    if rows:
        flash(f"config name '{config_name}' already exists", "danger")
        return redirect(url_for("new_config"))
    
    post_accounts = request.form.getlist("postAccounts")
    # Check if all accounts belong to the user
    acc_count = query_db("SELECT COUNT(id) AS count FROM ConnectedAccounts WHERE id IN (?) AND user_id = ?;", post_accounts, session["user_id"])
    acc_count = acc_count[0]["count"]
    
    if acc_count != len(post_accounts):
        flash("Invalid post accounts", "danger")
        return redirect(url_for("new_config"))
    
    if not request.form.get("splitType"):
        query_db("BEGIN TRANSACTION")
        
        configId = str(uuid4())
        query_db("INSERT INTO video_configurations (id, user_id, config_name, created_at) VALUES (?, ?, ?, ?);", 
            configId, session["user_id"], config_name, datetime.datetime.now()
        )   
        
        for account_id in post_accounts:
            query_db("INSERT INTO video_config_account (config_id, social_account_id) VALUES (?, ?);", configId, account_id) 
        
        query_db("COMMIT")

        flash("Successfully registered", "success")
        return redirect(url_for("dashboard"))
    
    # Ensure video position was submitted
    if not request.form.get("videoPosition"):
        flash("must provide video position", "danger")
        return redirect(url_for("new_config"))
    
    # Ensure split percentage was submitted
    if not request.form.get("videoPercentage"):
        flash("must provide video split percentage", "danger")
        return redirect(url_for("new_config"))
    
    # Ensure at least one gameplay was submitted
    if not request.form.getlist("gameplay"):
        flash("must provide at least one gameplay", "danger")
        return redirect(url_for("new_config"))
    
    # Check for a valid split type
    splitType = request.form["splitType"]
    if splitType not in ["horizontal", "vertical"]:
        flash("invalid split type", "danger")
        return redirect(url_for("new_config"))
    
    # Check for a valid video position
    videoPosition = request.form["videoPosition"]
    if splitType == "horizontal":
        if videoPosition not in ["top", "bottom"]:
            flash("invalid videoPosition", "danger")
            return redirect(url_for("new_config"))
    elif splitType == "vertical":
        if videoPosition not in ["left", "right"]:
            flash("invalid videoPosition", "danger")
            return redirect(url_for("new_config"))
        
        # Ensure processing option was submitted
        if not request.form.get("processingOptions"):
            flash("must provid processing options", "danger")
            return redirect(url_for("new_config"))      
    else:
        flash("must provide a valid splitType", "danger")
        return redirect(url_for("new_config"))
    
    # Check split percentage is on range
    videoPercentage = request.form.get("videoPercentage", type=int)
    if not (videoPercentage >= 0 and videoPercentage <= 100):
        flash("video percentage out of range", "danger")
        return redirect(url_for("new_config"))
    
    # Check the process type
    process_option = request.form.get("processingOptions", "crop")
    if process_option not in ["crop", "fit"]:
        flash("must provide a valid processing option", "danger")
        return redirect(url_for("new_config"))
    
    configId = str(uuid4())
    query_db("BEGIN TRANSACTION")    
    query_db("INSERT INTO video_configurations (id, user_id, config_name, split_type, video_position, original_video_percentage, edit_type, created_at) VALUES (?, ?, ?, ? , ?, ?, ?, ?);", 
        configId, session["user_id"], config_name, splitType, videoPosition, videoPercentage, process_option, datetime.datetime.now()
    )
    for v_id in request.form.getlist("gameplay"):
        query_db("INSERT INTO config_gameplays (config_id, gameplay_id) VALUES (?, ?);", configId, v_id)

    for account_id in post_accounts:
        query_db("INSERT INTO video_config_account (config_id, social_account_id) VALUES (?, ?);", configId, account_id)
    
    query_db("COMMIT")
    
    flash("Successfully registered", "success")
    return redirect(url_for("dashboard"))
        
@app.route("/delete", methods=["POST"])
@login_required
def delete_config():
    configId = request.form.get("config_id")
    rows = query_db("DELETE FROM video_configurations WHERE id = ? AND user_id = ?;", configId, session["user_id"])
    if rows:
        flash("Successfully deleted!", "success")
    else:
        flash("Couldn't delete, try again", "danger")
    
    return redirect(url_for("dashboard"))  

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "GET":
        username = query_db("SELECT ig_username FROM users WHERE id = ?;", session["user_id"])
        connectedAccounts = query_db("SELECT * FROM ConnectedAccounts WHERE user_id = ?;", session["user_id"])
        return render_template("settings.html", ig_username=username[0].get("ig_username"), accounts=connectedAccounts)
    
    # Ensure instagram username was submitted
    if not request.form.get("igUsername"):
        flash("must provide instagram username", "danger")
        return redirect(url_for("settings"))
    
    # Check if username is valid
    igUsername = instagram_username(request.form["igUsername"])
    if not igUsername:
        flash("instagram username must be valid", "danger")
        return redirect(url_for("settings"))
    
    update_row = query_db("UPDATE users SET ig_username = ? WHERE id = ?;", igUsername, session["user_id"])
    if update_row:
        flash("Successfully updated", "success")
    else:
        flash("Couldn't save ig_username", "danger")
    
    return redirect(url_for("dashboard"))
        
@app.route("/progress")
@login_required
def progress():
    query = """
    SELECT
        vj.id,
        vj.caption,
        g.title,
        vc.config_name,
        vj.status,
        vj.created_at
    FROM 
        video_jobs vj 
    LEFT JOIN 
        video_configurations vc ON vj.config_id = vc.id 
    LEFT JOIN 
        gameplays g ON vj.gameplay_id = g.id 
    WHERE
        vj.user_id = ?
    ORDER BY 
        vj.created_at DESC;
    """
    rows = query_db(query, session["user_id"])
    return render_template("progress.html", processes=(rows or []))

@app.route("/output")
@login_required
def output():
    return render_template("output.html")
   
@app.route("/explore")
@login_required
def explore():
    """Explore gameplays videos"""
    page = request.args.get("page", 1, type=int)
    gameplays = query_db("SELECT * FROM gameplays LIMIT ? OFFSET ?;", Config.gameplayPerPage, (page - 1) * Config.gameplayPerPage)
    return jsonify(gameplays or [])

@app.route("/output", methods=["POST"])
@login_required
def get_output():
    """Retrieve processed video"""
    query = """
    SELECT
        vj.id,
        vj.caption
    FROM 
        video_jobs vj 
    WHERE
        vj.user_id = ? AND vj.status = 'completed'
    ORDER BY 
        vj.created_at DESC
    LIMIT
        ? 
    OFFSET ?;
    """
    page = request.form.get("page", 1, type=int)
    output_videos = query_db(query, session["user_id"], Config.outputPerPage, (page - 1) * Config.outputPerPage)
    return jsonify(output_videos or [])

@app.route("/thumbnail/<string:id>")
@login_required
def thumbnail(id: str):
    """Send video thumbail"""
    return send_from_directory(Config.thumbnailPath, id)

@app.route("/download/<string:id>")
@login_required
def download(id: str):
    """Download video with id"""
    
    query = """
    SELECT
        *
    FROM 
        video_jobs vj 
    WHERE
        vj.user_id = ? AND vj.status = 'completed' AND vj.id = ?;
    """
    rows = query_db(query, session["user_id"], id)
    if not rows:
        abort(404, "Video not found")

   # Ensure the file exists on disk
    video_path = os.path.join(Config.outputDirectory, id + ".mp4")
    if not os.path.exists(video_path):
        abort(404, "File not found")
    
    as_attachment = request.args.get("attachment", "false").lower() == "true"
    return send_from_directory(Config.outputDirectory, id + ".mp4",as_attachment=as_attachment, mimetype="video/mp4")

@app.route("/reels/<string:file_name>")
def video_reels(file_name: str):
   # Ensure the file exists on disk
    video_path = os.path.join(Config.outputDirectory, file_name)
    if not os.path.exists(video_path):
        abort(404, "File not found")
    
    return send_from_directory(Config.outputDirectory, file_name, as_attachment=True)

@app.route("/tiktok/auth")
@login_required
def tiktok_authorize():
    provide_data = Config.tiktokAuth
    # Generate a random string for the state parameter
    session["oauth2_tk_state"] = secrets.token_urlsafe(16)
    
    # Create a query string with all Oauth2 params
    qs = urlencode({
        "client_key": provide_data["clientId"],
        "redirect_uri": "https://86010cwj-5000.uks1.devtunnels.ms" + url_for("tiktok_callback"),
        "response_type": "code",
        "scope": ",".join(provide_data["scopes"]),
        "state": session["oauth2_tk_state"]
    })
    auth_url = provide_data["authUrl"] + "?" + qs
    return redirect(auth_url)   

@app.route("/tiktok/callback")
@login_required
def tiktok_callback():
    # if there was an authentication error, flash the error messages and exit
    if 'error' in request.args:
        for k, v in request.args.items():
            if k.startswith('error'):
                flash(f'{k}: {v}', "danger")
        return redirect(url_for('settings'))
    
    if request.args['state'] != session.get('oauth2_tk_state'):
        flash("invalid request", "danger")
        return redirect(url_for("settings"))
    
    # make sure that the authorization code is present
    if 'code' not in request.args:
        flash("invalid request", "danger")
        return redirect(url_for("settings")) 

    provide_data = Config.tiktokAuth
    granted_permissions = request.args.get("scopes").split(",")
    # Ensure the necessary permissions are granted.
    for scope in provide_data["scopes"]:
        if scope not in granted_permissions:
            flash(f"Permission {scope} is required!", "danger")
            return redirect(url_for("settings"))
 
    # exchange the authorization code for an access token
    response = requests.post(provide_data["tokenUrl"], data={
        "client_key": provide_data["clientId"],
        "client_secret": provide_data["clientSecret"],
        "code": request.args["code"],
        "grant_type": "authorization_code",
        "redirect_uri": "https://86010cwj-5000.uks1.devtunnels.ms" + url_for("tiktok_callback") 
        }, headers={"Accept": "application/json"}
    )  
    if not response.ok:
        flash("Server error, please try again", "danger")
        return redirect(url_for("settings"))
    
    tokenInfo = response.json()
    access_token = tokenInfo.get("access_token")
    if not access_token:
        flash("Server error, please try again", "danger")
        return redirect(url_for("settings"))

    # Use the access token to get the user's profile
    response = requests.get(provide_data["userInfoUrl"], params={"fields": "username,open_id"}, headers={
        'Authorization': 'Bearer ' + access_token,
        'Accept': 'application/json',
    })
    if not response.ok:
        flash("Server error, please try again", "danger")
        return redirect(url_for("settings"))
    
    user_profile = response.json().get("data", {}).get("user")
    if not user_profile:
        flash("Server error, please try again", "danger")
        return redirect(url_for("settings"))
    
    query = """
        INSERT INTO 
            ConnectedAccounts 
        (   
            user_id,
            platform,
            account_id,
            account_username,
            account_token,
            refresh_token,
            connected_at,
            token_expires_at,
            refresh_expires_in
        ) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
    added = query_db(
        query,
        session["user_id"],
        "tiktok",
        user_profile.get("open_id"),
        user_profile.get("username"),
        tokenInfo.get("access_token"),
        tokenInfo.get("refresh_token"),
        datetime.datetime.now(),
        datetime.datetime.now() + datetime.timedelta(seconds=tokenInfo.get("expires_in")),
        datetime.datetime.now() + datetime.timedelta(seconds=tokenInfo.get("refresh_expires_in"))
    )
    if not added:
        flash("Couldn't register account", "danger")
    else: 
        flash(f"Account '{user_profile.get('username')}' successfully added", "success")
    
    return redirect(url_for("settings")) 

@app.route("/ig/auth")
@login_required
def instagram_authorize():
    """Redirect to instagram auth page"""
    
    provide_data = Config.instagramAuth
    # Generate a random string for the state parameter
    session["oauth2_ig_state"] = secrets.token_urlsafe(16)
    
    # Create a query string with all Oauth2 params
    qs = urlencode({
        "client_id": provide_data["clientId"],
        "enable_fb_login": 0,
        "force_authentication": 1,
        "redirect_uri": "https://86010cwj-5000.uks1.devtunnels.ms" + url_for("instagram_callback"),
        "response_type": "code",
        "scope": " ".join(provide_data["scopes"]),
        "state": session["oauth2_ig_state"]
    })
    auth_url = provide_data["authUrl"] + "?" + qs
    return redirect(auth_url)   

@app.route("/ig/callback")
@login_required
def instagram_callback():
    # if there was an authentication error, flash the error messages and exit
    if 'error' in request.args:
        for k, v in request.args.items():
            if k.startswith('error'):
                flash(f'{k}: {v}', "danger")
        return redirect(url_for('settings'))
    
    if request.args['state'] != session.get('oauth2_ig_state'):
        flash("invalid request", "danger")
        return redirect(url_for("settings"))
    
    # make sure that the authorization code is present
    if 'code' not in request.args:
        flash("invalid request", "danger")
        return redirect(url_for("settings")) 

    provide_data = Config.instagramAuth

    # exchange the authorization code for a short lived access token
    response = requests.post(provide_data["tokenUrl"], data={
        "client_id": provide_data["clientId"],
        "client_secret": provide_data["clientSecret"],
        "code": request.args["code"].rstrip("#_"),
        "grant_type": "authorization_code",
        "redirect_uri": "https://86010cwj-5000.uks1.devtunnels.ms" + url_for("instagram_callback")
        }, headers={"Accept": "application/json"}
    )  
    if not response.ok:
        flash("Server error, please try again", "danger")
        return redirect(url_for("settings"))
    
    token_info = response.json()

    access_token = token_info.get("access_token")
    granted_permissions = token_info.get("permissions")
    
    if not (access_token and granted_permissions):
        flash("Server error, please try again", "danger")
        return redirect(url_for("settings"))
    
    # Ensure the necessary permissions are granted.
    for scope in provide_data["scopes"]:
        if scope not in granted_permissions:
            flash(f"Permission {scope} is required!", "danger")
            return redirect(url_for("settings"))
  
    # Exchnage the short lived token with the long lived token
    response = requests.get(provide_data["longTokenUrl"], params={
        "access_token": access_token,
        "client_secret": provide_data["clientSecret"],
        "grant_type": "ig_exchange_token"
    }, headers={"Accept": "application/json"})
    if not response.ok:
        print(response.text)
        flash("Server error, please try again", "danger")
        return redirect(url_for("settings"))

    token_info = response.json()
    
    access_token = token_info.get("access_token") # Long lived
    if not (access_token and token_info.get("expires_in")):
        flash("Server error, please try again", "danger")
        return redirect(url_for("settings"))
    
    expire_in = datetime.datetime.now() + datetime.timedelta(seconds=token_info.get("expires_in")) # Number of seconds until token expires

    # Get user profile
    graph = GraphApi(access_token=access_token)
    profile = graph.getProfileMe()
    if not profile:
        flash("Server error, Please try again", "danger")
        return redirect(url_for("settings"))
    
    rows = query_db("SELECT * FROM ConnectedAccounts WHERE account_id = ? AND platform = 'instagram';", profile.get("id"))
    if rows:
        if rows[0]["user_id"] == session["user_id"]:
            update_account = query_db("UPDATE ConnectedAccounts SET account_token = ?, token_expires_at = ? WHERE account_id = ?;", 
                access_token, expire_in, profile.get("id")
            )
            if not update_account:
                flash("Server error try again", "danger")
                return redirect(url_for("settings"))
        else:
            flash("Account already connected with other user", "danger")
            return redirect(url_for("settings"))
    else:
        query = """
        INSERT INTO 
            ConnectedAccounts (user_id, platform, account_id, account_username, account_token, account_type, connected_at, token_expires_at) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        account_id = query_db(query, session["user_id"], "instagram", profile.get("id"), profile.get("username"), access_token, profile["account_type"], datetime.datetime.now(), expire_in)
        if not account_id:
            flash("Server error try again", "danger")
            return redirect(url_for("settings"))
        
    flash("Account connected successfully", "success")
    return redirect(url_for("settings"))
    
@app.route("/authorize")
def oauth2_authorize():
    """Redirect to Google auth screen"""
    if session.get("user_id"):
        return redirect(url_for("index")) # TODO: redirect to agent route
    
    session["user_id"] = 1
    return redirect("/")
    provide_data = Config.googleAuth
    # Generate a random string for the state parameter
    session["oauth2_state"] = secrets.token_urlsafe(16)
    
    # Create a query string with all Oauth2 params
    qs = urlencode({
        "client_id": provide_data["clientId"],
        "redirect_uri": url_for("oauth2_callback", _external=True),
        "response_type": "code",
        "scope": " ".join(provide_data["scopes"]),
        "state": session["oauth2_state"]
    })
    auth_url = provide_data["authUrl"] + "?" + qs
    return redirect(auth_url)   

@app.route("/auth/callback")
def oauth2_callback():
    """Authenticate users with Google"""
    if session.get("user_id"):
        return redirect(url_for("index"))

    # if there was an authentication error, flash the error messages and exit
    if 'error' in request.args:
        for k, v in request.args.items():
            if k.startswith('error'):
                flash(f'{k}: {v}', "danger")
        return redirect(url_for('index'))
    
    if request.args['state'] != session.get('oauth2_state'):
        flash("invalid request", "danger")
        return redirect(url_for("index"))
    
    # make sure that the authorization code is present
    if 'code' not in request.args:
        flash("invalid request", "danger")
        return redirect(url_for("index")) 

    provide_data = Config.googleAuth

    # exchange the authorization code for an access token
    response = requests.post(provide_data["tokenUrl"], data={
        "client_id": provide_data["clientId"],
        "client_secret": provide_data["clientSecret"],
        "code": request.args["code"],
        "grant_type": "authorization_code",
        "redirect_uri": url_for("oauth2_callback", _external=True) 
        }, headers={"Accept": "application/json"}
    )  
    if not response.ok:
        flash("Server error, please try again", "danger")
        return redirect(url_for("index"))
    
    access_token = response.json().get("access_token")
    if not access_token:
        flash("Server error, please try again", "danger")
        return redirect(url_for("index"))

    # Use the access token to get the user's profile
    response = requests.get(provide_data["userInfoUrl"], headers={
        'Authorization': 'Bearer ' + access_token,
        'Accept': 'application/json',
    })
    if not response.ok:
        flash("Server error, please try again", "danger")
        return redirect(url_for("index"))
    
    user_profile = response.json()
    
    # find or create the user in the database
    rows = query_db("SELECT * FROM Users WHERE email = ?;", user_profile["email"])
    if len(rows) == 0:
        user_id = query_db("INSERT INTO Users (email, first_name, last_name, register_date) VALUES (?, ?, ?, ?);",
            user_profile["email"],
            user_profile.get("given_name"),
            user_profile.get("family_name"),
            datetime.datetime.now()
        )
        session["user_id"] = user_id
    else:
        session["user_id"] = rows[0]["id"]
    
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/webhook")
def igverify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not (request.args.get("hub.verify_token") == Config.verifyToken):
            return "Verification token missmatch", 403
        return request.args['hub.challenge'], 200
    else:
        return "Got /webhook but without needed parameters.", 400

@app.route("/webhook", methods=["POST"])
@verify_signature
def webhook():
    if not request.is_json:
        return "Got /webhook but it's not json", 400
    
    # Get the JSON data from the request
    body = request.get_json()
    print("\033[32mReceived webhook\033[0m")

    if body.get("object") == "instagram":
        process_ig_webhook(body)              
        return "EVENT_RECEIVED", 200

    # Return a '404 Not Found' if event is not recognized
    return "unrecognized POST to webhook", 404


def process_ig_webhook(body):
    for entry in body.get("entry", []):
        if "messaging" not in entry:
            print("No messaging field in entry. Possibly a webhook test.")
            return
        for webhookEvent in entry.get("messaging", []):
            # Discard uninteresting events
            if "message" in webhookEvent and webhookEvent["message"].get("is_echo"):
                print("Got an echo")
                return
            
            # Get the sender IGSID
            senderIgsid = webhookEvent["sender"]["id"]
            rows = query_db("SELECT * FROM users WHERE ig_id = ?;", senderIgsid)
            if not rows:
                graph_api = GraphApi()
                user_profile = graph_api.getUserProfile(senderIgsid)
                if user_profile and "username" in user_profile:
                    update_count = query_db(
                        "UPDATE users SET ig_id = ? WHERE ig_username = ?;",
                        senderIgsid,
                        user_profile["username"].lower()
                    )
                    if update_count:
                        rows = query_db("SELECT * FROM users WHERE ig_id = ?;", senderIgsid)
                    else:
                        send_ig_reply.delay(senderIgsid, "Signup to autosplit!")
                        return 
                else:
                    return 
            
            user_configs = query_db("SELECT * FROM video_configurations WHERE user_id = ?;", rows[0]["id"])
            if not user_configs:
                send_ig_reply.delay(senderIgsid, "No video configurations found. Set up a new one now to customize your video edits")
                return 
            
            if webhookEvent.get("message"):    
                message = webhookEvent["message"]        
                  
                if message.get("attachments"):
                    attachment = message["attachments"][0]
                    if attachment.get("type") == "ig_reel":
                        payload = attachment["payload"]
                        # Instruct a default task to to process the video inside redis if no configuration name arrives in 20     
                        task_obj = default_ig_process.apply_async(args=[senderIgsid, rows[0], payload, user_configs], countdown=Config.countdown)
                        print(f"task_id: {task_obj.id} will start after 20sec...")
                        
                        task_data = {"task_id": task_obj.id, "payload": payload, "timestamp": webhookEvent["timestamp"]}
                        # Save the payload inside redis until a configuration name arrives
                        print(f"Set task_id: {task_obj.id} into redis")
                        # TODO: need to add key expiration
                        redis_client.set(f"{senderIgsid}_{payload['reel_video_id']}", json.dumps(task_data))
                
                elif message.get("text"):
                    msg = message["text"].strip().lower()
                    config = None
                    for cg in user_configs:
                        if cg.get("config_name") == msg:
                            config = cg
                    
                    if not config:
                        print("Configuration doesn't exists...")
                        return 
                    
                    current_task = None
                    max_timestamp = float('-inf')
                    # Get all reels sent by user
                    for key in redis_client.scan_iter(f"{senderIgsid}_*"):
                        task_data = redis_client.get(key)
                        if task_data:
                            task = json.loads(task_data)
                            if task["timestamp"] > max_timestamp:
                                current_task = task
                                max_timestamp = task["timestamp"]
                    
                    if current_task:       
                        task_id = current_task['task_id']
                        
                        task_obj = default_ig_process.AsyncResult(task_id)
                        task_obj.revoke(terminate=True)
                        print(f"Task {task_id} revoked.")
                        
                        # Delete task from redis
                        print(f"Delete task with id: {current_task.get('task_id')} from redis...")
                        redis_client.delete(f"{senderIgsid}_{current_task['payload']['reel_video_id']}")
                        
                        ig_process.delay(rows[0], current_task["payload"], config)
                    
@celery.task
def default_ig_process(senderIgsid, user, payload, configs):
    # Delete the reel video from redis
    redis_client.delete(f"{senderIgsid}_{payload['reel_video_id']}")
    # Check user have default config            
    if user.get("default_config_id"): 
        for config in configs:
            if config.get("id") == user["default_config_id"]:
                vid_ps = VideoProcess(user, payload, config)
                vid_ps.start_process()     
                return 
    else:
        print(f"No default configuration for user: {user['email']}")
        send_ig_reply.delay(senderIgsid, "No default configuration found...")
        
            
@celery.task   
def ig_process(user, payload, config_name):
    print(f"{config_name} config processing video url: {payload['url']}")
    vid_ps = VideoProcess(user, payload, config_name)
    vid_ps.start_process() 
    
    
@celery.task
def send_ig_reply(sender_ig_id, message):
    print(f"Sender id: {sender_ig_id}, message: {message}")
    return 
