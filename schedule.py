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
        self.title = row[0]
        if len(row) <= 1 or int(row[1]) > 1000:
            self.votes = None
        else:
            self.votes = int(row[1])
        if len(row) <= 2 or not row[2]:
            self.date_suggested = "2000-01-01"
        else:
            self.date_suggested = row[2]
        self.attribution = None if len(row) <= 3 else row[3]
        self.provider = None if len(row) <= 4 else row[4]
        self.notes = None if len(row) <= 5 else row[5]
        self.completed = None if len(row) <= 6 else row[6]
        self.game_id = None if len(row) <= 7 else row[7]
        self.override_id = None if len(row) <= 8 else row[8]
        self.cover = "" if len(row) <= 9 else row[9]
        self.description = "" if len(row) <= 10 else row[10]


def write_game(f: TextIOWrapper, game: ListGame):
    image_path = None
    if game.cover:
        image_path = downloader.fetch_image(game.cover)
    desc = game.description if game.description else ""
    title = game.title
    provider = game.provider if game.provider else ""

    if game.notes:
        title += f" - {game.notes}"
    f.write('        <div class="game">\n')
    if image_path:
        f.write(
            f'          <div class="realimage" style="background-image: url({image_path})"></div>\n'
        )
    else:
        f.write('          <div class="fakeimage">?</div>\n')
    f.write(f"          <h2>{title}</h2>\n")
    if game.completed:
        f.write(f'          <div class="votes">Completed on {game.completed}</div>\n')
    if game.votes:
        f.write(
            f"          <div class=\"votes\">Suggested by {game.attribution} on {game.date_suggested} <span class=\"votesreal\">({game.votes} vote{'' if game.votes == 1 else 's'})</span></div>"
        )
        pass
    else:
        f.write('          <div class="votes">Streamer chosen</div>')
    if game.provider:
        f.write(f'          <div class="provider">Provider: {provider}</div>')
    f.write(f'          <div class="description">{desc}</div>')
    f.write("        </div>\n")


SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")
SPREADSHEET_RANGE = SPREADSHEET_NAME + "!" + os.getenv("SPREADSHEET_RANGE")


def main():
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """

    try:
        service = build("sheets", "v4", credentials=get_creds())

        # First fetch the current sheet values
        sheet = service.spreadsheets()
        result = (
            sheet.values()
            .get(spreadsheetId=SPREADSHEET_ID, range=SPREADSHEET_RANGE)
            .execute()
        )
        values = result.get("values", [])

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

            if len(row) > 8 and row[7] != row[8]:
                # Override id doesn't match detected id, so prepare to start over
                row[7] = None
                print(f"Row {row_num} is overridden")

            if len(row) <= 7 or not row[7]:
                # New addition to the list!
                print(f"Row {row_num} is new")
                game = None
                if len(row) > 8 and row[8]:
                    game = moby.get_game_for_id(row[8])

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
                        "range": f"{SPREADSHEET_NAME}!H{row_num}",
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
            values = result.get("values", [])

        values = list(ListGame(row) for row in values[1:] if row[0])

        values = list(
            sorted(
                values,
                key=lambda g: (
                    (10000 - g.votes) if g.votes else 999999,
                    g.date_suggested,
                ),
            )
        )

        # sort the data
        god_chosen = list(g for g in values if not g.votes)
        pleb_chosen = list(g for g in values if g.votes)

        final_list: List[ListGame] = list()
        completed_list: List[ListGame] = list()

        while god_chosen or pleb_chosen:
            # first pull an item from god list
            if god_chosen:
                g = god_chosen.pop(0)
                # but only if not completed
                if not g.completed:
                    final_list.append(g)
                else:
                    completed_list.append(g)

            # same thing, but pleb
            if pleb_chosen:
                g = pleb_chosen.pop(0)
                if not g.completed:
                    final_list.append(g)
                else:
                    completed_list.append(g)
        
        completed_list.sort(key=lambda r: r.completed)

        now = datetime.now(UTC)
        now_stamp = now.strftime('%b {}, %Y at {}:%M:%S').format(now.day, now.hour)

        with open("schedule.html", "w", encoding="utf-8") as f:
            f.writelines(
                [
                    "<!doctype html>\n",
                    "<html>\n",
                    "  <head>\n",
                    "    <title>Upcoming Games List</title>\n",
                    '    <link rel="stylesheet" href="style.css"></link>\n',
                    "  </head>\n",
                    "  <body>\n",
                    "    <h1>Upcoming Games</h1>\n",
                    f"    <p>Last updated: {now_stamp} UTC</p>\n",
                    '    <div class="gamelist">\n',
                ]
            )

            for game in final_list:
                write_game(f, game)
            f.write("    </div>\n")

            if completed_list:
                f.write("    <h1>Completed Games</h1>\n")
                f.write('    <div class="gamelist">\n')
                for game in completed_list:
                    write_game(f, game)

                f.write("    </div>\n")

            f.writelines(["  <div>Data provided by <a target='_blank' href='https://www.mobygames.com/'>MobyGames</a></div></body>\n", "</html>\n"])

    except HttpError as err:
        print(err)


if __name__ == "__main__":
    main()
