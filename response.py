def genText(text):
    response = {
        "text": text
    }
    return response

def genWebUrlButton(text, url):
    response = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": text,
                "buttons": [
                    {
                        "type": "web_url",
                        "url": url,
                        "title": "Visit our website"
                    }
                ]
            }
        }
    }
    return response