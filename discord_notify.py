import datetime as dt
import requests
import sqlite3
import pytz
import json
import os

import exposure_parser

def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]

current_datetime = dt.datetime.now(pytz.timezone("Australia/Perth"))
unix_timestamp = int(current_datetime.timestamp())

with open("config.json") as f:
    config = json.load(f)
DB_FILE = config["database_file"]
DISCORD_WEBHOOKS = config["discord_webhooks"]

directory, file = os.path.split(DB_FILE)
if not os.path.exists(directory):
    os.makedirs(directory)
conn = sqlite3.connect(DB_FILE)

last_run_file = ".last_run"
if os.path.exists(last_run_file):
    with open(last_run_file) as f:
        LAST_RUN = dt.datetime.fromtimestamp(int(f.read()))
else:
    LAST_RUN = dt.datetime.fromtimestamp(0)

# Create tables if needed
table_create = """
CREATE TABLE IF NOT EXISTS ExposureSites (
    ID              INTEGER NOT NULL UNIQUE,
    Latitude        REAL    NOT NULL       ,
    Longitude       REAL    NOT NULL       ,
    StartTime       INTEGER NOT NULL       ,
    EndTime         INTEGER                ,
    Location        TEXT                   ,
    Advice          TEXT                   ,
    FirstSeen       INTEGER NOT NULL       ,
    LastSeen        INTEGER NOT NULL       ,
    PRIMARY KEY("ID" AUTOINCREMENT)
);"""
conn.execute(table_create)
conn.commit()

exposures = \
    exposure_parser.murdoch_exposures()             + \
    exposure_parser.uwa_exposures()                 + \
    exposure_parser.ecu_exposures()                 + \
    exposure_parser.civilian_exposures(True)        + \
    exposure_parser.wahealth_exposures(LAST_RUN)

with open(last_run_file, "w+") as f:
    f.write(str(unix_timestamp))

new_exposures = []

for exposure in exposures:
    query = "SELECT ID FROM ExposureSites WHERE Latitude = ? AND Longitude = ? AND StartTime = ? AND EndTime = ?;"
    start_time = int(exposure.start_time.timestamp())
    end_time = int(exposure.end_time.timestamp())
    result = conn.execute(query, (exposure.address.latitude, exposure.address.longitude, start_time, end_time))
    if not result.fetchall():
        new_exposures.append(exposure)
        query = "INSERT INTO ExposureSites (Latitude, Longitude, StartTime, EndTime, Location, Advice, FirstSeen, LastSeen) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        conn.execute(query, (exposure.address.latitude, exposure.address.longitude, start_time, end_time, exposure.location_descriptor, exposure.advice, unix_timestamp, unix_timestamp))
conn.commit()

for url in DISCORD_WEBHOOKS:
    for exposures in chunks(new_exposures, 10):
        data = {
            "embeds": []
        }
        for exposure in exposures:
            embed = {
                "title": "COVID-19 Exposure Site",
                "fields": [],
                "color": 583168
            }
            if exposure.start_time == exposure.end_time:
                # (Unknown times)
                embed["fields"].append({"name": "Date", "value": exposure.start_time.strftime('%-d/%-m/%Y'), "inline": False})
            else:
                embed["fields"].append({"name": "Start Time", "value": exposure.start_time.strftime('%-H:%M %-d/%-m/%Y'), "inline": True})
                if exposure.end_time:
                    embed["fields"].append({"name": "End Time", "value": exposure.end_time.strftime('%-H:%M %-d/%-m/%Y'), "inline": True})
            address = ", ".join(exposure.address.address.split(", ")[:-3])
            embed["fields"].append({"name": "Address", "value": address, "inline": False})
            if exposure.location_descriptor:
                embed["fields"].append({"name": "Location", "value": exposure.location_descriptor, "inline": False})
            if exposure.advice:
                embed["fields"].append({"name": "Advice", "value": exposure.advice, "inline": False})
            data["embeds"].append(embed)
        result = requests.post(url, json=data)
        if 200 <= result.status_code < 300:
            print(f"Webhook sent {result.status_code}")
        else:
            print(f"Not sent with {result.status_code}, response:\n{result.json()}")