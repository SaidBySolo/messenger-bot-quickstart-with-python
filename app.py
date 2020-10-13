import os

import aiohttp

from sanic import Sanic
from sanic import response
from sanic.response import json
from sanic.exceptions import abort

app = Sanic(__name__)

PAGE_ACCESS_TOKEN = os.environ["PAGE_ACCESS_TOKEN"]

# Handles messages events
async def call_send_api(sender_psid, response):
    # Construct the message body
    request_body = {"recipient": {"id": sender_psid}, "message": response}
    qs = {"access_token": PAGE_ACCESS_TOKEN}

    # Send the HTTP request to the Messenger Platform
    try:
        async with aiohttp.ClientSession() as cs:
            async with cs.post(
                "https://graph.facebook.com/v2.6/me/messages",
                json=request_body,
                params=qs,
            ) as r:
                print("message sent")
    except Exception as err:
        print("Unable to send message:" + err)


# Handles messages events
async def handle_message(sender_psid, received_message):

    # Check if the message contains text
    if received_message.get("text"):
        # Create the payload for a basic text message
        # will be added to the body of our request to the Send API
        response = {
            "text": f"""You sent the message: "{received_message["text"]}". Now send me an attachment!"""
        }
    elif received_message.get("attachments"):
        # Gets the URL of the message attachment
        attachment_url = received_message["attachments"][0]["payload"]["url"]
        response = {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": [
                        {
                            "title": "Is this the right picture?",
                            "subtitle": "Tap a button to answer.",
                            "image_url": attachment_url,
                            "buttons": [
                                {
                                    "type": "postback",
                                    "title": "Yes!",
                                    "payload": "yes",
                                },
                                {
                                    "type": "postback",
                                    "title": "No!",
                                    "payload": "no",
                                },
                            ],
                        }
                    ],
                },
            }
        }
    # Sends the response message
    await call_send_api(sender_psid, response)


# Handles messaging_postbacks events
async def handle_postback(sender_psid, received_postback):

    # Get the payload for the postback
    payload = received_postback["payload"]

    # Set the response based on the postback payload
    if payload == "yes":
        response = {"text": "Thanks"}
    elif payload == "no":
        response = {"text": "Oops, try sending another image."}

    await call_send_api(sender_psid, response)


@app.get("/webhook")
async def _verify_webhook(request):

    VERIFY_TOKEN = "<YOUR_VERIFY_TOKEN>"

    # Parse params from the webhook verification request
    challenge = request.args.get("hub.challenge")
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")

    # Check if a token and mode were sent
    if mode and token:

        # Check the mode and token sent are correct
        if mode == "subscribe" and token == VERIFY_TOKEN:

            # Respond with 200 OK and challenge token from the request
            print("WEBHOOK_VERIFIED")
            return response.text(challenge)

        else:
            # Responds with '403 Forbidden' if verify tokens do not match
            return abort(403)


@app.post("/webhook")
async def _webhook(request):
    # Parse the request body from the POST
    body = request.json

    # Check the webhook event is from a Page subscription
    if body.get("object") == "page":

        # Iterate over each entry - there may be multiple if batched
        for messaging in body.get("entry"):

            # Get the webhook event. entry.messaging is an array, but
            # will only ever contain one event, so we get index 0
            webhook_event = messaging["messaging"][0]
            print(webhook_event)

            # Get the sender PSID
            sender_psid = webhook_event["sender"]["id"]

            # Check if the event is a message or postback and
            # pass the event to the appropriate handler function
            if webhook_event.get("message"):
                await handle_message(sender_psid, webhook_event["message"])
            elif webhook_event.get("postback"):
                await handle_postback(sender_psid, webhook_event["postback"])

            return json({"status": 200})

    else:
        # Return a '404 Not Found' if event is not from a page subscription
        return abort(404)


if __name__ == "__main__":
    app.run("0.0.0.0", 8000)
