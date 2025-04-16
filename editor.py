import os
from config import Config
from moviepy import *
import shutil
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Editor:
    def __init__(self, video_path, gameplay_path, config) -> None:
        try:
            self.main_video = VideoFileClip(video_path)
            self.gameplay_video = VideoFileClip(gameplay_path).without_audio()
        except OSError as e:
            logging.error(f"Failed to load video files: {e}")
            raise
        
        self.config = config
        self.clips = []
        
        try:       
            self.width, self.height = self.main_video.size
            # Compute percentage
            self.percentage = self.config["original_video_percentage"] / 100.0
        except KeyError as e:
            logging.error(f"Missing config key: {e}")
            raise
        except Exception as e:
            logging.error(f"Error during initialization: {e}")
            raise
        
    def start_editing(self, video_id):
        # Set final duration to match the original video.
        try:            
            duration = self.main_video.duration
            if self.gameplay_video.duration > duration:
                self.gameplay_video = self.gameplay_video.subclipped(0, duration)
            else:
                self.gameplay_video = self.gameplay_video.with_effects([vfx.Loop(duration=duration)])
                
            if self.config["split_type"] == "vertical":
                if self.config["edit_type"] == "fit":
                    self._vertical_fit()
                elif self.config["edit_type"] == "crop":
                    self._vertical_crop()
                else:
                    logging.error("Invalid split_type in config")
                    raise ValueError("Invalid split_type")
                
            elif self.config["split_type"] == "horizontal":
                self._horizontal()
            else:
                logging.error("Invalid split_type in config")
                raise ValueError("Invalid split_type")
            
            final_clip = clips_array(
                self.clips
            )
            
            output_path = os.path.join(Config.outputDirectory, video_id + ".mp4")

            final_clip.write_videofile(
                output_path,
                fps=60,
                bitrate="15M",
                preset="slow", # Slower encoding for higher quality
                temp_audiofile_path="tmp_audio"
            )    
            return output_path
        
        except Exception as e:
            logging.exception(f"Error during video editing: {e}")
            raise
        
        finally:
            self._cleanup()
      
    def _cleanup(self):
        """Release resources"""
        try:
            if hasattr(self, 'main_video'):
                self.main_video.close()
            if hasattr(self, 'gameplay_video'):
                self.gameplay_video.close()
        except Exception as e:
            logging.warning(f"Error during cleanup: {e}")
              
    def _horizontal(self):
        # Compute target height
        try:      
            main_height = int(self.percentage * self.height)
            gameplay_height = self.height - main_height
            
            # Crop the main video
            self.main_video = Editor.rule_of_thirds_crop(self.main_video, main_height)
            # Crop and resize gameplay
            self.gameplay_video = Editor.smart_resize(self.gameplay_video, self.width, gameplay_height)

            self.gameplay_video = Editor.center_weighted_crop(
                self.gameplay_video,
                self.width,
                gameplay_height
            )
            
            if self.config["video_position"] == "top":
                self.clips.append([self.main_video])
                self.clips.append([self.gameplay_video])
            else:
                self.clips.append([self.gameplay_video])
                self.clips.append([self.main_video])
        except Exception as e:
            logging.error(f"Error in horizontal layout: {e}")
            raise
    
    def _vertical_crop(self):
        # Compute target width
        try:       
            main_width = int(self.percentage * self.width)
            gameplay_width = self.width - main_width 
            
            # Crop the main and gameplay video
            self.main_video = Editor.center_weighted_crop(self.main_video, main_width, self.height)
            # Resize gameplay
            self.gameplay_video = Editor.smart_resize(self.gameplay_video, gameplay_width, self.height)
            
            self.gameplay_video = Editor.center_weighted_crop(self.gameplay_video, gameplay_width, self.height)
            
            if self.config["video_position"] == "left":
                self.clips.append([self.main_video, self.gameplay_video])
            else:
                self.clips.append([self.gameplay_video, self.main_video])
        except Exception as e:
            logging.error(f"Error in vertical_crop: {e}")
            raise
            
    def _vertical_fit(self):
        # Crop gameplay video
        try:            
            self.gameplay_video = Editor.smart_resize(self.gameplay_video, self.width, self.height)
            self.gameplay_video = Editor.center_weighted_crop(self.gameplay_video, self.width, self.height)
            
            if self.config["video_position"] == "left":
                self.clips.append([self.main_video, self.gameplay_video])
            else:
                self.clips.append([self.gameplay_video, self.main_video])
        except Exception as e:
            logging.error(f"Error in vertical fit: {e}")
            raise
        
    @staticmethod
    def center_weighted_crop(clip, target_width, target_height):
        try:
            original_width, original_height = clip.size

            if target_height < original_height:
                pixels_to_remove = original_height - target_height

                top = pixels_to_remove // 2
                bottom = top + target_height

                clip = clip.cropped(y1=top, y2=bottom)

            if target_width < original_width:
                pixels_to_remove = original_width - target_width
                left = pixels_to_remove // 2
                right = left + target_width

                clip = clip.cropped(x1=left, x2=right)

            return clip
        except Exception as e:
            logging.error(f"Error in center_weighted_crop: {e}")
            raise
        
    @staticmethod
    def rule_of_thirds_crop(clip, target_height):
        try:            
            original_width, original_height = clip.size

            # Calculate the three horizontal zones (top/middle/bottom)
            zone_height = original_height // 3

            top_zone = zone_height
            middle_zone = zone_height * 2
            bottom_zone = zone_height

            # How much we need to remove
            pixels_to_remove = original_height - target_height

            # Case 1: No cropping needed
            if pixels_to_remove <= 0:
                return clip

            # Case 2: Can remove entirely from bottom
            if pixels_to_remove <= bottom_zone:
                return clip.cropped(y2=original_height - pixels_to_remove)

            # Case 3: Need to remove from bottom + distribute remainder
            else:
                # First remove entire bottom zone
                bottom_crop = bottom_zone
                remaining_crop = pixels_to_remove - bottom_crop

                # Split remaining between top and middle
                top_crop = int(remaining_crop * 0.3) # Remove 30% from the top and the remaining from middle
                middle_crop = remaining_crop - top_crop 

                # Apply cropping
                return clip.cropped(
                    y1=top_crop,
                    y2=(original_height - middle_crop -  bottom_crop)
                )
        except Exception as e:
            logging.error(f"Error in rule_of_thirds_crop: {e}")
            raise
        
    @staticmethod
    def smart_resize(clip, target_width, target_height):
        try:           
            if clip.size[0] < target_width or clip.size[1] < target_height:
                # Scale up to cover at least one dimension
                scale_factor = max(target_width/clip.w, target_height/clip.h)
                return clip.resized(scale_factor)
            return clip
        except Exception as e:
            logging.error(f"Error in smart_resize: {e}")
            raise
        
    @staticmethod
    def copycat(video_path):
        try:
            return shutil.copy(video_path, Config.outputDirectory)
        except Exception as e:
            logging.error(f"Error copying video file: {e}")
            raise
