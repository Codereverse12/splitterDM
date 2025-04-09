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
        if self.payload.get("type") == "attachment":
            query_db("INSERT INTO video_jobs (id, user_id, caption, config_id, created_at) VALUES (?, ?, ?, ?, ?);", self.job_id, self.user["id"], self.payload.get('title'), self.config['id'], datetime.datetime.now())
            # Download video
            video_path = self.download_attachment_video(self.payload["url"])
            if not video_path:
                self._update_status("Failed to download video", "failed")
                return 
        else:
            query_db("INSERT INTO video_jobs (id, user_id, config_id, created_at) VALUES (?, ?, ?, ?);", self.job_id, self.user["id"], self.config['id'], datetime.datetime.now())
            video_path = self.download_link_video(self.payload["url"])
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
        else:  
            gameplay_path = self.get_gameplay()
            if not gameplay_path:
                self._update_status("Couldn't get gameplay video", "failed")
                return 
            
            self._update_status(None, "processing")
            try:
                edit_obj = Editor(video_path, gameplay_path, self.config)
            except Exception as es:
                print(es)
                self._update_status("error during processing", "failed")
                return 
            video_url = edit_obj.start_editing(self.job_id)
            if video_url:
                self._update_status(None, "completed")
            else:
                self._update_status(None, "failed")
    
    def download_attachment_video(self, url):
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
    
    
    def _tiktok_download(self, url):
        res = requests.post("https://tikwm.com/api/", data={
            "url": url,
            "count": 12,
            "cursor": 0,
            "web": 1,
            "hd": 1
        })
        if res.status_code != 200:
            print(f"Error downloading video with url: {url}")
            return
        
        data = res.json()
        if not data.get("data"):
            print(f"Couldn't get tiktok video data url: {url}")
            return
        
        v_url = "https://tikwm.com"
        
        video = data["data"]

        if video.get("play"):
            v_url += video["play"]
        else:
            print(f"Couldn't get video to download for url: {url}")
            return

        res = requests.get(v_url)
        
        file_path = os.path.join(Config.reelsDirectory, self.job_id + "." + v_url.rsplit(".")[-1])
        with open(file_path, "wb") as file:
            for chunk in res.iter_content(100000):
                file.write(chunk)
        
        query_db("UPDATE video_jobs SET caption = ? WHERE id = ?;", video.get("title"), self.job_id)

        return file_path   
        
        
    def download_link_video(self, url):
        print(f"Download video with url: {url}")

        if "tiktok" in self.payload["url"]:
            return self._tiktok_download(url)
            
    def get_gameplay(self):
        config_videos = query_db("SELECT gameplay_id FROM config_gameplays WHERE config_id = ?;", self.config["id"])
        if not config_videos:
            return 
        
        n = randint(0, len(config_videos) - 1)
        gameplay_id = config_videos[n]["gameplay_id"]
        
        # Update the video_job with gameplay id
        query_db("UPDATE video_jobs SET gameplay_id = ? WHERE id = ?;", gameplay_id, self.job_id)
        return os.path.join(Config.gameplayDirectory, config_videos[n]["gameplay_id"] + ".mp4")
    
    def _update_status(self, message, status):
        if message:
            query_db("UPDATE video_jobs SET processing_errors = ?, status = ? WHERE id = ?;", message, status, self.job_id)
        else:
            query_db("UPDATE video_jobs SET status = ? WHERE id = ?;", status, self.job_id)