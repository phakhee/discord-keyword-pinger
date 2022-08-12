import pyrebase
import os
import uuid
import re
from datetime import datetime
from classes.Singleton import Singleton
from dotenv import load_dotenv


class StreamHandler(metaclass=Singleton):
    load_dotenv()
    keywords = []
    stream = None

    def __init__(self):
        self.config = {
            "apiKey": os.getenv("FIREBASE_API_KEY"),
            "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
            "databaseURL": os.getenv("FIREBASE_DB_URL"),
            "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET")
        }

        self.firebase = pyrebase.initialize_app(self.config)
        self.db = self.firebase.database()

        self.synced = False

    def start(self):
        self.init()
        self.stream = self.db.child("keywords").stream(self.stream_handler)

    def init(self):
        # Sync existing keywords first.
        keywords = self.db.child("keywords").get()

        if keywords.each():
            for keyword in keywords.each():
                self.keywords.append({
                    keyword.key(): keyword.val()
                })
        else:
            self.synced = True

    def stream_handler(self, message):
        # When new keyword is added.
        if message["data"] and self.synced and type(message["data"]) is dict:
            self.keywords.append({
                message["path"].replace("/", ""): message["data"]
            })

        # When delay is adjusted.
        elif "/delay" in message["path"] and message["data"]:
            for keywords in self.keywords:
                keywords_id = list(keywords.keys())[0]

                if keywords_id == re.search("/(.*)/delay", message["path"]).group(1):
                    keywords[keywords_id]["delay"] = message["data"]

        # When keyword is deleted.
        elif message["path"] and message["data"] is None:
            self.keywords = [
                keywords for keywords in self.keywords
                if list(keywords.keys())[0] != message["path"].replace("/", "")
            ]
        else:
            self.synced = True

    def all_keywords(self):
        keywords_entries = self.db.child("keywords").get()
        keywords = []

        if keywords_entries.each():
            for keywords_entry in keywords_entries.each():
                keywords.append({
                    keywords_entry.key(): keywords_entry.val()
                })

        return keywords

    def add_keywords(self, data):
        entry_id = uuid.uuid4()
        self.db.child("keywords").child(entry_id).set(data)

        return str(entry_id)

    def remove_keywords(self, tbr_keywords, channel_id):
        keywords_entries = self.db.child("keywords").get()
        deleted = []

        if keywords_entries.each():
            for keywords in keywords_entries:
                keywords_id = keywords.key()
                keywords_values = " ".join(keywords.val()["keywords"])
                keywords_channel_id = keywords.val()["channel"]["id"]

                if tbr_keywords == keywords_values and keywords_channel_id == channel_id:
                    self.db.child("keywords").child(keywords_id).update(None)
                    self.db.child("deleted_keywords").push({
                        "id": keywords_id,
                        "keywords": tbr_keywords,
                        "deleted_at": datetime.now().replace(microsecond=0).isoformat()
                    })
                    deleted.append(keywords_id)

        return deleted

    def add_ping(self, keywords_id):
        ping_exists = []
        all_pings = self.db.child("pings").get()

        if all_pings.each():
            pings = [{ping.key(): ping.val()} for ping in all_pings.each()]
            ping_exists = [
                ping for ping in pings
                if ping[list(ping.keys())[0]]["keywords_id"] == keywords_id
            ]

        if len(ping_exists) != 0:
            ping_id = list(ping_exists[0].keys())[0]

            self.db.child("pings").child(ping_id).update({
                "keywords_id": keywords_id,
                "pinged_at": datetime.now().replace(microsecond=0).isoformat()
            })

        else:
            entry_id = uuid.uuid4()

            self.db.child("pings").child(entry_id).set({
                "keywords_id": keywords_id,
                "pinged_at": datetime.now().replace(microsecond=0).isoformat()
            })

    def check_existing_ping(self, keywords_id, delay):
        all_pings = self.db.child("pings").get()

        if all_pings.each():
            pings = [{ping.key(): ping.val()} for ping in all_pings.each()]
            # Check on existing pings if there is already one with keyword_id X.
            ping_exists = [
                ping for ping in pings
                if ping[list(ping.keys())[0]]["keywords_id"] == keywords_id
            ]

            if len(ping_exists) != 0:
                ping_id = list(ping_exists[0].keys())[0]
                ping = ping_exists[0][ping_id]

                current_time = datetime.now()
                previous_ping_time = datetime.fromisoformat(ping["pinged_at"])
                time_difference = (current_time - previous_ping_time).total_seconds()

                if time_difference >= delay:
                    return True
                else:
                    return False

            else:
                return True

        return True


stream_handler = StreamHandler()
