from config import Config
import re
from my_db import query_db
import requests
from uuid import uuid4
import os
import datetime
import time
from random import randint
from editor import Editor
from graph_api import GraphApi

class VideoProcessor:
    def __init__(self, user, payload, config) -> None:
        self.user = user
        self.config = config
        self.payload = payload
        self.job_id = str(uuid4())

    def start_process(self):
        # Start a video job
        query_db("INSERT INTO video_jobs (id, user_id, caption, config_id, created_at) VALUES (?, ?, ?, ?, ?);", self.job_id, self.user["id"], self.payload.get('title'), self.config['id'], datetime.datetime.now())
        
        video_path = self.download_video(self.payload["url"])
        if not video_path:
            self._update_status("Failed to download video", "failed")
            return 
        # Update job status to download
        self._update_status(None, "downloaded")
        
        if not self.config.get("split_type"):
            copy_path = Editor.copycat(video_path)
            if copy_path:
                self._update_status(None, "completed")
            else:   
                self._update_status("Couldn't copy video", "failed")
                return 
        else:  
            gameplay_path = self.get_gameplay()
            if not gameplay_path:
                self._update_status("Couldn't get gameplay video", "failed")
                return 
            
            self._update_status(None, "processing")
            
            edit_obj = Editor(video_path, gameplay_path, self.config)
            video_url = edit_obj.start_editing(self.job_id)
            if video_url:
                self._update_status(None, "completed")
            else:
                self._update_status(None, "failed")
                return 

        # Post Automatically
        print("Starting automatic post...")
        title = self.payload.get('title')
        accounts = self.get_social_accounts()
        for acc in accounts:
            query_db("INSERT INTO post_status (video_id, social_account_id, status) VALUES (?, ?, ?);", self.job_id, acc["id"], "posting")
            
            is_posted = self.postVideo(Config.reelsUrl + self.job_id + ".mp4", title, acc)   
            status = "posted" if is_posted else "failed"
            
            self._update_post_status(status, acc["id"])   
    
    def download_video(self, url):
        print(f"Download video with url: {url}")
        
        res = requests.get(url)    
        if res.status_code != 200:
            print(f"Error downloading video with url: {url}")
            return
        
        file_path = os.path.join(Config.reelsDirectory, self.job_id + ".mp4")
        with open(file_path, "wb") as file:
            for chunk in res.iter_content(100000):
                file.write(chunk)
        
        return file_path        

    def get_gameplay(self):
        config_videos = query_db("SELECT gameplay_id FROM config_gameplays WHERE config_id = ?;", self.config["id"])
        if not config_videos:
            return 
        
        n = randint(0, len(config_videos) - 1)
        gameplay_id = config_videos[n]["gameplay_id"]
        
        # Update the video_job with gameplay id
        query_db("UPDATE video_jobs SET gameplay_id = ? WHERE id = ?;", gameplay_id, self.job_id)
        return os.path.join(Config.gameplayDirectory, config_videos[n]["gameplay_id"] + ".mp4")
    
    def postVideo(self, video_url, title, acc):
        graph_obj = GraphApi(access_token=acc["account_token"])
        container = graph_obj.getReelContainer(video_url, caption=title)
        if not container:
            return 
        
        isUploaded = self.isUploadSuccessful(graph_obj, 0, container.get("id"))
        if isUploaded:
            return graph_obj.publishReelVideo(container.get("id"))
        return None 
    
    def isUploadSuccessful(self, graph_obj, retry_count, id):
        if retry_count > 3000:
            return False
        status = graph_obj.getMediaUploadStatus(id)
        if status.get("status_code") != "FINISHED":
            time.sleep(30)
            return self.isUploadSuccessful(graph_obj, retry_count + 1, id)
        return True
    
    def get_social_accounts(self):
        accounts = query_db("SELECT * FROM video_config_account cg JOIN ConnectedAccounts ca ON cg.social_account_id = ca.id WHERE cg.config_id = ?;", self.config["id"])        
        return accounts or []
    
    def _update_status(self, message, status):
        if message:
            query_db("UPDATE video_jobs SET processing_errors = ?, status = ? WHERE id = ?;", message, status, self.job_id)
        else:
            query_db("UPDATE video_jobs SET status = ? WHERE id = ?;", status, self.job_id)

    def _update_post_status(self, status, account_id):
        query_db("UPDATE post_status SET status = ? WHERE video_id = ? AND social_account_id = ?;", status, self.job_id, account_id)