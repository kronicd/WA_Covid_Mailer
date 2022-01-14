#!/usr/bin/env python3


import requests
import lxml.html
import sqlite3
import json
from pprint import pprint
import smtplib, ssl
import pytz
from datetime import datetime
import os
import shutil
import subprocess
import time


waGovUrl = "https://www.healthywa.wa.gov.au/COVID19locations"
date_time = datetime.now(pytz.timezone("Australia/Perth")).strftime("%d/%m/%Y %H:%M:%S")


### CONFIGURATION ITEMS ###

# Debug mode disables sending of alerts
debug = True

# Database location
db_file = "/path/to/exposures.db"  # will be created on first use

# Email details
emailAlerts = False
smtpServ = ""
smtpPort = ""
fromAddr = ""
replyAddr = ""
subjLine = f"Alert: Updated WA covid-19 exposure sites ({date_time})"
destAddr = [
    "email1@example.com", 
    "email2@example.com"
]

# Slack Alerts
slackAlerts = False
webhook_urls = [
    "https://hooks.slack.com/services/XXXXXXX/XXXXXXX/XXXXXXX",
    "https://hooks.slack.com/services/XXXXXXX/XXXXXXX/XXXXXXX"
]

# Discord Alerts
discordAlerts = False
discord_webhook_urls = [
    "https://discordapp.com/api/webhooks/XXXXXXX/XXXXXXX",
    "https://discordapp.com/api/webhooks/XXXXXXX/XXXXXXX"
]

# Dreamhost Announce
dreamhostAnounces = False
apiKey = ""
listDomain = ""
listName = ""
subjLine = f"Alert: Updated WA covid-19 exposure sites ({date_time})"

# Error Alert Email
adminAlerts = False
adminSmtpServ = ""
adminSmtpPort = ""
adminFromAddr = ""
adminSmtpUser = ""
adminSmtpPass = ""
AdminReplyAddr = ""
AdminSubjLine = f"Alert: WA Covid Mailer Error ({date_time})"
AdminDestAddr = [
    "email1@example.com", 
    "email2@example.com"
]

### END OF CONFIGURATION ITEMS


if debug:
    db_file = "exposures-debug.db"


def create_connection(db_file):

    conn = None
    try:
        conn = sqlite3.connect(db_file, isolation_level=None)
    except Error as e:
        print(f"something went wrong: {e}")

    # create tables if needed
    query = (
        "SELECT count(name) FROM sqlite_master WHERE type='table' AND name='exposures';"
    )

    result = conn.execute(query)

    if result.fetchone()[0] == 1:
        pass
    else:
        print("creating table...")
        table_create = """ CREATE TABLE IF NOT EXISTS exposures (
                            id integer PRIMARY KEY,
                            datentime text,
                            suburb text,
                            location text,
                            updated text,
                            advice text
                        ); """
        conn.execute(table_create)
        conn.commit()

    return conn


def sendEmails(body):

    for destEmail in destAddr:

        message = f"""To: {destEmail}
From: {fromAddr}
Reply-To: {replyAddr}
Subject: {subjLine}


{body}.""".encode("ascii", "replace")

        try:
            context = ssl.create_default_context()

            with smtplib.SMTP_SSL(smtpServ, smtpPort, context=context) as server:
                server.sendmail(fromAddr, destEmail, message)
                print(f"Email sent to {destEmail}")
        except smtplib.SMTPException as e:
            print("SMTP error occurred: " + str(e))


def sendAdminAlert(errorMsg):

    if(adminAlerts):
        for destEmail in AdminDestAddr:

            message = f"""To: {AdminDestAddr}
From: {adminFromAddr}
Reply-To: {AdminReplyAddr}
Subject: {AdminSubjLine}


{errorMsg}.""".encode("ascii", "replace")

            try:
                context = ssl.create_default_context()

                with smtplib.SMTP_SSL(adminSmtpServ, adminSmtpPort, context=context) as server:
                    server.sendmail(adminFromAddr, adminDestEmail, message)
                    print(f"Email sent to {destEmail}")
            except smtplib.SMTPException as e:
                print("SMTP error occurred: " + str(e))
    else:
        print("Admin alerts disabled")


def post_message_to_slack(text, blocks=None):

    for webhook_url in webhook_urls:
        slack_data = {"text": text}

        response = requests.post(
            webhook_url,
            data=json.dumps(slack_data),
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise ValueError(
                "Request to slack returned an error %s, the response is:\n%s"
                % (response.status_code, response.text)
            )

        print("Slack sent")


def post_message_to_discord(text, blocks=None):

    for discord_webhook_url in discord_webhook_urls:

        # Discord doesn't let us post more than 2000 characters at a time
        # so we need to split and make individual posts every 2 seconds to avoid rate limits.
        # This may spam notifications depending on your server settings
        discord_text = text.split('\n\n')
        alert_total = (len(discord_text))
        alert_number = 0

        for alert in discord_text:
            alert_number += 1

            discord_data = {"content": alert}

            response = requests.post(
                discord_webhook_url,
                data=json.dumps(discord_data),
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200|204: #Discord returns 204 no data on success
                raise ValueError(
                    "Request to discord returned an error %s, the response is:\n%s"
                    % (response.status_code, response.text)
                )

            print("Discord sent %s of %s" % (alert_number, alert_total))
            time.sleep(2)        


def sendDhAnnounce(comms):

    url = "https://api.dreamhost.com/"

    bodyParams = {
        "key": "somevalue",
    }
    data = {
        "key": apiKey,
        "cmd": "announcement_list-post_announcement",
        "listname": listName,
        "domain": listDomain,
        "subject": subjLine,
        "message": comms,
        "charset": "utf-8",
        "type": "text",
        "duplicate_ok": "1",
    }

    x = requests.post(url, data=data)

    print(x.text)
    return x.status_code


def getDetails():

    req = requests.get(waGovUrl)

    if req.status_code != 200:
        print(f"Failed to fetch page: {req.reason}")
        raise Exception("reqest_not_ok")

    doc = lxml.html.fromstring(req.content)

    sites_table = doc.xpath('//table[@id="locationTable"]')[0][1]
    rows = sites_table.xpath(".//tr")

    # check for proper header
    header = doc.xpath('//table[@id="locationTable"]')[0][0]
    headerRows = header.xpath(".//th")

    if (headerRows[0].text_content() == 'Exposure date & time' and 
    headerRows[1].text_content() == 'Suburb' and
    headerRows[2].text_content() == 'Location' and
    headerRows[3].text_content() == 'Date updated' and
    headerRows[4].text_content() == 'Health advice'):
        pass
    else:
        rows = ""

    if len(rows) < 1:
        print(f"found no data")
        raise Exception("table_parse_fail")

    return rows


def cleanString(location):

    newLoc = ""
    location = location.replace("\xa0", "")
    for line in location.split("\n"):
        newLoc = newLoc + line.lstrip().rstrip() + ", "
    return newLoc.rstrip(", ").replace(", , ", ", ").rstrip("\r\n")


def buildDetails(exposure):
    datentime = cleanString(exposure[1].text_content())
    suburb = cleanString(exposure[2].text_content())
    location = cleanString(exposure[3].text_content())
    updated = cleanString(exposure[4].text_content())
    advice = cleanString(exposure[5].text_content())

    exposure_details = f"""Date and Time: {datentime}
Suburb: {suburb}
Location: {location}
Updated: {updated}
Advice: {advice}\n\n"""

    exposure_details = exposure_details.rstrip("\r\n") + "\n\n"

    return exposure_details

def filterExistingExposures(exposure):

    # examine each exposure
    # if it is in the DB already, do nothing
    # if it is not in the DB: add it to our alerts list
    alerts = []
    for exposure in exposures:

        datentime = cleanString(exposure[1].text_content())
        suburb = cleanString(exposure[2].text_content())
        location = cleanString(exposure[3].text_content())
        updated = cleanString(exposure[4].text_content())
        advice = cleanString(exposure[5].text_content())

        query = """SELECT count(id) FROM exposures WHERE 
                    datentime = ? 
                    AND suburb = ?
                    AND location = ?
                    AND updated = ?
                    AND advice = ?;"""

        args = (datentime, suburb, location, updated, advice)
        result = dbconn.execute(query, args)

        if result.fetchone()[0] > 0:
            pass
            # print('exposure exists')
        else:
            alerts.append(exposure)

    return alerts

# load sqlite3
dbconn = create_connection(db_file)

# backup db incase things go bad
shutil.copy(db_file, f"{db_file}.bak")

# get exposures
try:
    exposures = getDetails()
except:
    sendAdminAlert("Unable to fetch data, please investigate")
    exit()

# filter list of exposures to remove known/previously seen exposures
alerts = filterExistingExposures(exposures)

# for each new exposure add it to the DB and add it to a string for comms
comms = ""

for exposure in alerts:

    comms = comms + buildDetails(exposure)

    datentime = cleanString(exposure[1].text_content())
    suburb = cleanString(exposure[2].text_content())
    location = cleanString(exposure[3].text_content())
    updated = cleanString(exposure[4].text_content())
    advice = cleanString(exposure[5].text_content())

    query = f"""INSERT INTO exposures (datentime, suburb, location, updated, advice) 
                VALUES (?,?,?,?,?) """

    args = (datentime, suburb, location, updated, advice)
    result = dbconn.execute(query, args)

    if debug:
        print(comms)


# kludge ugh
mailPostSuccess = 200

if not debug:

    if len(comms) > 0 and emailAlerts:
        sendEmails(comms)

    if len(comms) > 0 and slackAlerts:
        post_message_to_slack(comms)

    if len(comms) > 0 and discordAlerts:
        post_message_to_discord(comms)

    if len(comms) > 0 and dreamhostAnounces:
        mailPostSuccess = sendDhAnnounce(comms)


dbconn.commit()
# we don't close as we're using autocommit, this results in greater 
# compatability with different versions of sqlite3

if len(comms) > 0 and dreamhostAnounces and mailPostSuccess != 200 and not debug:
    print(result)
    os.replace(f"{db_file}.bak", db_file)
    sendAdminAlert("Unable to send mail, please investigate")
else:
    os.remove(f"{db_file}.bak")
