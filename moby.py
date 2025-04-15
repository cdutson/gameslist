import os
import os.path
import requests
import time
from typing import List, Dict


class MobyGames:
    base_url = "https://api.mobygames.com/v2"

    def __init__(self):
        self.api_key = os.getenv("MOBY_API_KEY")
        if not self.api_key:
            raise Exception("No Moby API Key")
        self.last_call = 0

    def get_games_for_title(self, title) -> List[Dict]:
        arg = {
            "include": "title,description,official_url,covers",
            "title": title,
        }

        results = self.make_api_call("GET", "/games", arg)
        return results["games"]

    def get_game_for_id(self, id) -> List[Dict]:
        arg = {
            "include": "title,description,official_url,covers",
            "id": id
        }

        results = self.make_api_call("GET", f"/games", arg)
        gameData = None
        try:
            gameData = results["games"][0]
        except:
            gameData = None

        return gameData

    def make_api_call(self, method, url, args):
        now = time.time()
        limit_time = now - 2

        if self.last_call > limit_time:
            print("Sleeping to respect MobyGames API rate limit of 0.2 requests /second (5 seconds cap)...")
            time.sleep(6)

        self.last_call = time.time()

        resp = requests.request(
            method, self.base_url + url, params={**args, "api_key": self.api_key}
        )

        resp.raise_for_status()

        return resp.json()


if __name__ == "__main__":
    test = MobyGames()
    games = test.get_games_for_title("Another World")
    for t in games:
        print(t["game_id"], t["title"])
