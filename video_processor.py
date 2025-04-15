from config import Config
import re
import requests
from uuid import uuid4
import os
import datetime
import time
from random import randint
from editor import Editor
from graph_api import GraphApi
import yt_dlp
import logging
from bg_db import db

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class VideoProcessor:
    def __init__(self, user, payload, config) -> None:
        self.user = user
        self.config = config
        self.payload = payload
        self.job_id = str(uuid4())
        self.db = db()

    def start_process(self):
        video_url = self.payload.get("url")
        title = self.payload.get('title', "")
        is_attachment = self.payload.get("type") == "attachment"

        # Insert job
        try:
            if is_attachment:
                self.db.update("INSERT INTO video_jobs (id, user_id, caption, video_url, video_type, config_id, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s);", args=(self.job_id, self.user["id"], title, video_url, "instagram", self.config['id'], datetime.datetime.now()))
                video_path = self.download_attachment_video(video_url)
            else:
                self.db.update("INSERT INTO video_jobs (id, user_id, video_url, config_id, created_at) VALUES (%s, %s, %s, %s, %s);", args=(self.job_id, self.user["id"], video_url, self.config['id'], datetime.datetime.now()))
                video_path = self.download_link_video(video_url)
        except Exception as e:
            self._update_status("database or download error", "failed")
            return

        if not video_path:
            self._update_status("Failed to download video", "failed")
            return
        
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
                video_url = edit_obj.start_editing(self.job_id)
            except Exception as es:
                logging.error("Error during video editing")
                self._update_status("Error during video editing", "failed")
                return 
            
            if video_url:
                self._update_status(None, "completed")
            else:
                self._update_status(None, "failed")
    
    def download_attachment_video(self, url):
        logging.info(f"Downloading video from attachment URL: {url}")
        try:            
            res = requests.get(url)
            res.raise_for_status()
            
            file_path = os.path.join(Config.reelsDirectory, self.job_id + ".mp4")
            with open(file_path, "wb") as file:
                for chunk in res.iter_content(100000):
                    file.write(chunk)
            
            return file_path        
        except Exception as e:
            logging.error("Failed to download attachment video")
            return None
    
    def _tiktok_download(self, url):
        try:           
            res = requests.post("https://tikwm.com/api/", data={
                "url": url,
                "count": 12,
                "cursor": 0,
                "web": 1,
                "hd": 1
            })
            res.raise_for_status()

            data = res.json()
            video = data.get("data")
            
            if not video or not video.get("play"):
                logging.error(f"Couldn't extract TikTok video: {url}")
                return None
            
            v_url = "https://tikwm.com" + video["play"]

            res = requests.get(v_url)
            res.raise_for_status()
            
            file_path = os.path.join(Config.reelsDirectory, f"{self.job_id}.{v_url.rsplit('.')[-1]}")
            with open(file_path, "wb") as file:
                for chunk in res.iter_content(102400):
                    file.write(chunk)
            
            self.db.update("UPDATE video_jobs SET caption = %s, video_type = %s WHERE id = %s;", args=(video.get("title"), 'youtube', self.job_id))
            return file_path   
        except Exception as e:
            logging.error("TikTok download failed")
            return None
    
    @staticmethod
    def normalize_youtube_url(url: str) -> str:
        if "youtube.com/shorts/" in url:
            video_id = url.split("/shorts/")[1].split("?")[0]
            return f"https://www.youtube.com/watch?v={video_id}"
        return url

    def _yt_download(self, url):
        file_path = os.path.join(Config.reelsDirectory, self.job_id)
        try:
            ydl_opts = {
                'outtmpl': f'{file_path}.%(ext)s',
                'format': 'best[ext=mp4]',
                'quiet': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info.get("description"):
                    self.db.update("UPDATE video_jobs SET caption = %s, video_type = %s WHERE id = %s;", args=(info["description"], 'youtube', self.job_id))
                
                ext = info.get("ext", "mp4")
                return f"{file_path}.{ext}"

        except Exception as e:
            logging.error("YouTube download failed")
            return None
        
    def download_link_video(self, url):
        logging.info(f"Downloading video from link: {url}")
        try:
            if "tiktok" in url:
                return self._tiktok_download(url)
            elif "youtube" in url:
                return self._yt_download(self.normalize_youtube_url(url))
            else:
                logging.warning(f"Unsupported video platform for URL: {url}")
                return None
        except Exception as e:
            logging.error("Link download failed")
            return None
            
    def get_gameplay(self):
        try:        
            config_videos = self.db.fetch("SELECT gameplay_id FROM config_gameplays WHERE config_id = %s;", args=(self.config["id"],))
            if not config_videos:
                logging.warning("No gameplay videos found for config")
                return None
            
            gameplay_id = config_videos[randint(0, len(config_videos) - 1)]["gameplay_id"]
            self.db.update("UPDATE video_jobs SET gameplay_id = %s WHERE id = %s;", args=(gameplay_id, self.job_id))
            return os.path.join(Config.gameplayDirectory, f"{gameplay_id}.mp4")
        except Exception as e:
            logging.error("Failed to fetch gameplay video")
            return None
    
    def _update_status(self, message, status):
        try:    
            if message:
                self.db.update("UPDATE video_jobs SET processing_errors = %s, status = %s WHERE id = %s;", args=(message, status, self.job_id))
            else:
                self.db.update("UPDATE video_jobs SET status = %s WHERE id = %s;", args=(status, self.job_id))
            logging.info(f"Job {self.job_id} updated to status '{status}'")
        except Exception as e:
            logging.error("Failed to update job status")
