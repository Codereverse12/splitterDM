from graph_api import GraphApi
import response
import time

class Receive:
    def __init__(self, igid):
        """This is a class used to process webhookEvent"""
        self.igid = igid
        self.message = None
    
    def handleMessage(self, message):
        self.message = message
        responses = self.handleTextMessage()
        
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
        print(f"Received DM from user ({self.igid})") 
        url = "https://autosplitter.com"
        return response.genWebUrlButton(self.message, url)

    def sendMessage(self, message, delay=0):
        if not message:
            return
        requestBody = {
            "recipient": {
                "id": self.igid
            },
            "message": message
        }
        time.sleep(delay)
        GraphApi().callSendApi(requestBody)