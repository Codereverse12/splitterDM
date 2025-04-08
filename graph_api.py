from config import Config
import requests

class GraphApi:
    def __init__(self, access_token=Config.igAccessToken):
        # This is a class that contain Instagram API's
        self.access_token = access_token

    def getProfileMe(self):
        url = f'{Config.apiUrl}/me'
        params = {
            "access_token": self.access_token,
            "fields": "user_id,username,name,account_type"
        }
        response = requests.get(url, params=params,
            headers={"Accept": "application/json"}
        )
        if not response.ok:
            print(f"Could not load profile", response.reason)
            return
        return response.json()

    def getUserProfile(self, senderIgsid):
        url = f"{Config.apiUrl}/{senderIgsid}"
        params = {
            "access_token": self.access_token,
            "fields": "username,name,id"
        }
        response = requests.get(url, params=params,
            headers={"Accept": "application/json"}
        )
        if response.ok:
            userProfile = response.json()
            return {
                "user_id": userProfile["id"],
                "username": userProfile["username"],
                "name": userProfile["name"]
            }
        else:
            print(f"Could not load profile for {senderIgsid}: {response.reason}")

    def refreshLongLivedToken(self):
        url = f'{Config.apiDomain}/refresh_access_token'
        params = {
            "grant_type": "ig_refresh_token",
            "access_token": self.access_token
        }
        response = requests.get(url, params=params,
            headers={"Accept": "application/json"}
        )
        if not response.ok:
            print("error refreshing long lived token:", response.reason)
            return
        return response.json()


    def setIcebreakers(self, iceBreakers):
        url = f"{Config.apiUrl}/me/messenger_profile"
        params = {
            "access_token": self.access_token
        }
        json = {
            "platform": "instagram",
            "ice_breakers": iceBreakers
        }
        response = requests.post(url, params=params, json=json, headers={
            "Content-Type": "application/json"
        })
        if response.ok:
            print("Icebreakers have been set.")
        else:
            print(f"Error setting ice breakers {response.reason}")


    def setPersistentMenu(self, persistentMenu):
        url = f"{Config.apiUrl}/me/messenger_profile"
        params = {
            "access_token": self.access_token
        }
        json = {
            "platform": "instagram",
            "persistent_menu": persistentMenu
        }
        response = requests.post(url, params=params, json=json, headers={
            "Content-Type": "application/json"
        })
        if response.ok:
            print("Persistent Menu has been set.")
        else:
            print(f"Error setting Persistent Menu {response.reason}")


    def setIgSubscriptions(self):
        url = f"{Config.apiUrl}/me/subscribed_apps"
        params = {
            "access_token": self.access_token,
            "subscribed_fields": "messages,messaging_postbacks,comments,live_comments"
        }
        response = requests.post(url, params=params)
        if response.ok:
            print("IG subscriptions have been set.")
        else:
            print(f"Error setting IG subscriptions {response.reason}")
       
       
    def getReelContainer(self, videoUrl, caption=None, coverUrl=None):
        url = f"{Config.apiUrl}/me/media" 
        data = {
            "media_type": "REELS",
            "video_url": videoUrl ,
            "access_token": self.access_token,
            **({"caption": caption} if caption else {}),
            **({"cover_url": coverUrl} if coverUrl else {})
        }
        response = requests.post(url, data=data, headers={"Accept": "application/json"})
        if not response.ok:
            print(f"Error building media container: {response.reason}")
            return 
        return response.json()
    
    def publishReelVideo(self, containerId):
        url = f"{Config.apiUrl}/me/media_publish"
        data = {
            "creation_id": containerId,
            "access_token": self.access_token
        }
        response = requests.post(url, data=data, headers={"Accept": "application/json"})
        if not response.ok:
            print(f"Error publishing reel video: {response.reason}")
            return 
        return response.json()
    
    def getMediaUploadStatus(self, containerId):
        url = f"{Config.apiUrl}/{containerId}"
        params ={
            "fields": "status_code",
            "access_token": self.access_token
        }
        response = requests.get(url, params=params)
        if not response.ok:
            print(f"Error getting media status: {response.reason}")
            return 
        return response.json()
    
    def getPublishingLimit(self):
        url = f"{Config.apiUrl}/me/content_publishing_limit"
        params = {
            "fields": "config,quota_usage",
            "access_token": self.access_token
        }
        response = requests.get(url, params)
        if not response.ok:
            print(f"Error getting publishing limit: {response.reason}")
            return 
        return response.json()
    
    def getPermaLinkUri(self, mediaId):
        url = f"{Config.apiUrl}/{mediaId}"
        params = {
            "fields": "permalink",
            "access_token": self.access_token
        }
        response = requests.get(url, params)
        if not response.ok:
            print(f"Error getting permanent link: {response.reason}")
            return 
        return response.json()
    
    def callSendApi(self, requestBody):
        url = f"{Config.apiUrl}/me/messages"
        response = requests.post(url, headers={
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }, json=requestBody)
        if not response.ok:
            print(requestBody)
            print(f"Could not sent message. {response.reason}")
