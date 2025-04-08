def genText(text):
    response = {
        "text": text
    }
    return response

def genWebUrlButton(title, url):
    response = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": title,
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