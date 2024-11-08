from dotenv import load_dotenv

from io import TextIOWrapper
import os.path
import os
from datetime import datetime, UTC

from typing import List
from auth import get_creds
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from moby import MobyGames
from images import ImageDownloader

load_dotenv()

moby = MobyGames()
downloader = ImageDownloader("images")

class ListGame:
    def __init__(self, row):
        self.title = str(row[0])
        self.platform = str(row[1])
        self.count = str(row[2])
        self.notes = None if len(row) <= 4 else row[4]
        self.game_id = None if len(row) <= 5 else row[5]
        self.override_id = None if len(row) <= 6 else row[6]
        self.cover = "" if len(row) <= 7 else row[7]
        self.description = "" if len(row) <= 8 else row[8]

def write_game(f: TextIOWrapper, game: ListGame):
    image_path = None
    if game.cover:
        image_path = downloader.fetch_image(game.cover)
    desc = game.description if game.description else ""
    notes = f' - {game.notes}' if game.notes else ""

    f.write('        <div class="game">\n')
    f.write('        <div class="imageWrapper">\n')
    if image_path:
        f.write(
            f'          <div class="realimage" style="background-image: url({image_path})"></div>\n'
        )
    else:
        f.write('          <div class="fakeimage">?</div>\n')
    f.write(f"          <h3>{game.title}{notes}</h3>\n")
    f.write('</div>\n')
    f.write(f'          <div class="platform"><b>Platform:</b> {game.platform}</div>\n')
    f.write(f'          <div class="keycount"><b># of keys:</b> {game.count}</div>\n')
    f.write(f'          <div class="description">{desc}</div>')
    f.write("        </div>\n")

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = os.getenv("GIVEAWAY_SPREADSHEET_ID")
SPREADSHEET_NAME = os.getenv("GIVEAWAY_SPREADSHEET_NAME")
SPREADSHEET_RANGE = SPREADSHEET_NAME + "!" + os.getenv("GIVEAWAY_SPREADSHEET_RANGE")

def fetch_spreadsheet_values(sheet):
    return (
        sheet.values()
        .get(spreadsheetId=SPREADSHEET_ID, range=SPREADSHEET_RANGE)
        .execute().get("values", [])
    )

def main():
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """

    try:
        service = build("sheets", "v4", credentials=get_creds())

        # First fetch the current sheet values
        sheet = service.spreadsheets()
        values = fetch_spreadsheet_values(sheet)

        if not values:
            print("No data found.")
            return
        
        # Next, we need to examine the data to see if it needs to be fixed up
        updates = []
        row_num = 1
        for row in values[1:]:
            row_num += 1
            if not row[0]:
                continue

            if len(row) > 5 and row[5] != row[6]:
                # Override id doesn't match detected id, so prepare to start over
                row[5] = None
                print(f"Row {row_num} is overridden")

            if len(row) <= 5 or not row[5]:
                # New addition to the list!
                print(f"Row {row_num} is new")
                game = None
                if len(row) > 6 and row[6]:
                    game = moby.get_game_for_id(row[6])

                if not game:
                    games = moby.get_games_for_title(row[0])
                    if len(games) > 0:
                        for g in games:
                            if g["title"].lower() == row[0].lower():
                                game = g
                                break

                        if not game:
                            game = games[0]

                if not game:
                    game = {
                        "game_id": "unknown",
                        "description": "",
                        "title": row[0],
                        "sample_cover": {"image": None},
                    }

                updates.append(
                    {
                        "range": f"{SPREADSHEET_NAME}!A{row_num}",
                        "values": [[game["title"]]],
                    }
                )
                updates.append(
                    {
                        "range": f"{SPREADSHEET_NAME}!F{row_num}",
                        "values": [
                            [
                                game["game_id"],
                                game["game_id"],
                                game["sample_cover"]["image"],
                                game["description"],
                            ]
                        ],
                    }
                )
                # break

        if updates:
            print(f"Updating {len(updates)} chunks")
            sheet.values().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"valueInputOption": "RAW", "data": updates},
            ).execute()
            values = None

        if not values:
            # if we made any updates, re-fetch the sheet data
            values = fetch_spreadsheet_values(sheet)

        values = list(ListGame(row) for row in values[1:] if row[0])

        values = list(
            sorted(
                values,
                key=lambda g: (g.title),
            )
        )

        now = datetime.now(UTC)
        now_stamp = now.strftime('%b {}, %Y at {}:%M:%S').format(now.day, now.hour)

        with open("keys.html", "w", encoding="utf-8") as f:
            f.writelines(
                [
                    "<!doctype html>\n",
                    "<html>\n",
                    "  <head>\n",
                    "    <title>Free games via points redemption!</title>\n",
                    '    <link rel="stylesheet" href="style.css"></link>\n',
                    "  </head>\n",
                    "  <body>\n",
                    "    <h1>Available Keys</h1>\n",
                    f"    <p>Last updated: {now_stamp} UTC</p>\n",
                    '    <p>If you want a game key, all you have to do is come by a stream (<a href="https://twitch.tv/cdutson">https://twitch.tv/cdutson</a>) and redeem a free game using channel points!</p>\n'
                    '    <div class="gamelist">\n',
                ]
            )

            for game in values:
                write_game(f, game)
            f.write("    </div>\n")

            f.writelines(["  <footer><p>Data provided by <a target='_blank' href='https://www.mobygames.com/'>MobyGames</a></p></footer></body>\n", "</html>\n"])

    except HttpError as err:
        print(err)


if __name__ == "__main__":
    main()
