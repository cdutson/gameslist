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
        self.streamer_selected = row[1]
        self.votes = None if len(row) <= 2 else int(row[2])
        if len(row) <= 3 or not row[3]:
            self.date_suggested = "2000-01-01"
        else:
            self.date_suggested = row[3]
        
        self.attribution = None if len(row) <= 4 else row[4]
        self.provider = None if len(row) <= 5 else row[5]
        self.notes = None if len(row) <= 6 else row[6]
        self.started = None if len(row) <= 7 else row[7]
        self.completed = None if len(row) <= 8 else row[8]
        self.game_id = None if len(row) <= 9 else row[9]
        self.override_id = None if len(row) <= 10 else row[10]
        self.cover = "" if len(row) <= 11 else row[11]
        self.description = "" if len(row) <= 12 else row[12]
        self.official_url = "" if len(row) <= 13 else row [13]
        self.on_hold = None if len(row) <= 14 else row[14]

    def __repr__(self):
        return f"{self.title} - {self.votes} - {self.streamer_selected}"

def write_game(f: TextIOWrapper, game: ListGame):
    image_path = None
    if game.cover:
        image_path = downloader.fetch_image(game.cover)
    desc = game.description if game.description else ""
    title = f"{game.title}{" - " + game.notes if game.notes else ''}"

    provider = game.provider if game.provider else ""

    f.write('        <div class="game">\n')
    f.write('        <div class="imageWrapper">\n')
    if image_path:
        f.write(
            f'          <div class="realimage" style="background-image: url({image_path})"></div>\n'
        )
    else:
        f.write('          <div class="fakeimage">?</div>\n')
    if game.official_url:
        f.write(f"          <h3><a href='{game.official_url}' target='_blank'>{title}</a></h3>\n")
    else:
        f.write(f"          <h3>{title}</h3>\n")
    f.write('</div>\n')

    if game.started and not game.completed:
        f.write(f'          <div class="votes"><b>Started:</b> {game.started}</div>\n')
    if game.completed:
        f.write(f'          <div class="votes"><b>Completed:</b> {game.completed}</div>\n')
    if not game.streamer_selected and game.votes:
        f.write(
            f"          <div class=\"votes\"><b>Suggested by:</b> {game.attribution} on {game.date_suggested} <span class=\"votesreal\">({game.votes} vote{'' if game.votes == 1 else 's'})</span></div>"
        )
        pass
    else:
        f.write(f'          <div class="votes"><b>Streamer chosen</b>{f' <span class=\"votesreal\">({game.votes} vote{'' if game.votes == 1 else 's'})</span>' if game.votes else ''}</div>')
    if game.provider:
        f.write(f'          <div class="provider"><b>Provider:</b> {provider}</div>')
    f.write(f'          <div class="description">{desc}</div>')
    f.write("        </div>\n")


def write_list(f:TextIOWrapper, game_list: List[ListGame], title: str, description: str):
    f.write(f"    <h2>{title}</h2>\n")
    
    if description:
        f.write(f"    <p>{description}</p>")

    f.write('    <div class="gamelist">\n')
    
    for game in game_list:
        write_game(f, game)
    f.write("    </div>\n")


SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")
SPREADSHEET_RANGE = SPREADSHEET_NAME + "!" + os.getenv("SPREADSHEET_RANGE")

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

            if len(row) > 10 and row[9] != row[10]:
                # Override id doesn't match detected id, so prepare to start over
                row[9] = None
                print(f"Row {row_num} is overridden")

            if len(row) <= 9 or not row[9]:
                # New addition to the list!
                print(f"Row {row_num} is new")
                game = None
                if len(row) > 10 and row[10]:
                    game = moby.get_game_for_id(row[10])

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
                        "covers": None,
                        "official_url": ""
                    }

                updates.append(
                    {
                        "range": f"{SPREADSHEET_NAME}!A{row_num}",
                        "values": [[game["title"]]],
                    }
                )

                imgUrl = None

                try:
                    imgUrl = game["covers"][0]["images"][0]["image_url"]
                except:
                    imgUrl = None

                updates.append(
                    {
                        "range": f"{SPREADSHEET_NAME}!J{row_num}",
                        "values": [
                            [
                                game["game_id"],
                                game["game_id"],
                                imgUrl,
                                game["description"],
                                game["official_url"]
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
                key=lambda g: (
                    -abs(g.votes),
                    g.date_suggested,
                ),
            )
        )

        # sort the data
        to_play_list = list(g for g in values if not g.started and not g.completed and not g.on_hold)
        on_hold_list = list(g for g in values if g.on_hold)
        current_list: List[ListGame] = list(g for g in values if g.started and not g.completed and not g.on_hold)
        completed_list: List[ListGame] = list(g for g in values if g.completed and not g.on_hold)
        
        current_list.sort(key=lambda r: r.started)
        completed_list.sort(key=lambda r: r.completed, reverse=True)

        now = datetime.now(UTC)
        now_stamp = now.strftime('%b {}, %Y at {}:%M:%S').format(now.day, now.hour)

        schedule_subset = to_play_list[0:5]

        with open("schedule.txt", "w", encoding="utf-8") as t:
            comma_list = f"Next {len(schedule_subset)} games: "

            for game in schedule_subset:
                comma_list += f"{game.title} ({game.votes} votes) | "
            
            comma_list = comma_list[:-3]

            t.write(f"{comma_list}. Last updated {now_stamp}")

        with open("schedule.html", "w", encoding="utf-8") as f:
            f.writelines(
                [
                    "<!doctype html>\n",
                    "<html>\n",
                    "  <head>\n",
                    "    <title>Upcoming Games List</title>\n",
                    '    <link rel="stylesheet" href="style.css"></link>\n',
                    '    <link rel="preconnect" href="https://fonts.googleapis.com">\n',
                    '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n',
                    '    <link href="https://fonts.googleapis.com/css2?family=Montserrat:ital,wght@0,100..900;1,100..900&display=swap" rel="stylesheet">\n',
                    "  </head>\n",
                    "  <body>\n",
                    "     <h1>Games list</h1>\n",
                    f"    <p>Last updated: {now_stamp} UTC</p>\n",
                    "     <p>Here you can find all the games I have played, am playing, and will be playing soon.</p>\n"])
            
            if current_list:
                write_list(f, current_list, "Current Games", "What I'm playing right now.")
            
            if on_hold_list:
                write_list(f, on_hold_list, "On hold", "Can't play yet, or in a holding pattern for some reason.")

            write_list(f, to_play_list, "Upcoming Games", "What's coming up!")

            if completed_list:
                write_list(f, completed_list, "Completed Games", "This is a non-exhaustive list, trust me.")


            f.writelines(["  <footer><p>Data provided by <a target='_blank' href='https://www.mobygames.com/'>MobyGames</a></p></footer></body>\n", "</html>\n"])

    except HttpError as err:
        print(err)


if __name__ == "__main__":
    main()
