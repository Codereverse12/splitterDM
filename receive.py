import graph_api
import response
import time

class Receive:
    def __init__(self, user, webhookEvent):
        """This is a class used to process webhookEvent"""
        self.user = user
        self.webhookEvent = webhookEvent
    
    def handleMessage(self):
        event = self.webhookEvent

        responses = ""
        try:
            if event.get("message"):
                message = event["message"]
                
                if message.get("is_echo"):
                    return
                elif message.get("text"):
                    responses = self.handleTextMessage()
            elif event.get("postback"):
                responses = self.handlePostback()
        except Exception as exc:
            print(exc)
            responses = {
                "text": "An error has occured! We have been notified and will fix the issue shortly!"
            }
        
        if not responses:
            return
        
        if type(responses).__qualname__ == "list":
            delay = 0
            for res in responses:
                self.sendMessage(res, delay=delay * 2)
                delay += 1
        else:
            self.sendMessage(responses)
    
    def handleTextMessage(self):
        print(f"Received text from user {self.user['name']} ({self.user['user_id']}): \n", 
        self.webhookEvent["message"]["text"]
        )  
        title = "Signup to autosplitter ai"      
        url = "https://autosplitter.com"
        return response.genWebUrlButton(title, url)

    def handlePostback(self):
        print(f"Received Payload: {self.webhookEvent['postback']['payload']} for user {self.user['user_id']}")

        return None

    def sendMessage(self, message, delay=0):
        if not message:
            return
        requestBody = {
            "recipient": {
                "id": self.user["user_id"]
            },
            "message": message
        }
        time.sleep(delay)
        graph_api.callSendApi(requestBody)