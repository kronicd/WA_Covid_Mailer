#!/usr/bin/env python3


from datetime import date, datetime
from html.parser import HTMLParser
from pprint import pprint
import codecs
import csv
import json
import re
import lxml.html
import os
import pytz
import requests
import shutil
import smtplib, ssl
import sqlite3
import subprocess
import time
import traceback


waGovUrl = "https://www.healthywa.wa.gov.au/COVID19locations"
current_datetime = datetime.now(pytz.timezone("Australia/Perth"))
date_time = current_datetime.strftime("%d/%m/%Y %H:%M:%S")
unix_timestamp = int(current_datetime.timestamp())


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
        "SELECT name FROM sqlite_master WHERE type = 'table';"
    )

    result = conn.execute(query)

    tables = result.fetchall()

    required_tables = [
        'wahealth_exposures',
        'sheet_exposures',
        'ecu_exposures',
        'uwa_exposures',
        'murdoch_exposures',
        'curtin_exposures'
    ]
    
    for table in tables:
        while table[0] in required_tables:
            required_tables.remove(table[0])

    for exposures_table in required_tables:
        table_create = ""

        if exposures_table == 'wahealth_exposures':
            table_create = """
                CREATE TABLE IF NOT EXISTS wahealth_exposures (
                    id integer PRIMARY KEY,
                    datentime text,
                    suburb text,
                    location text,
                    updated text,
                    advice text,
                    first_seen integer,
                    last_seen integer
                );
            """
        elif exposures_table == 'sheet_exposures':
            table_create = """
                CREATE TABLE IF NOT EXISTS sheet_exposures (
                    id integer PRIMARY KEY,
                    datentime text,
                    location text,
                    suburb text,
                    first_seen integer,
                    last_seen integer
                );
            """
        elif exposures_table == 'ecu_exposures':
            table_create = """
                CREATE TABLE IF NOT EXISTS ecu_exposures (
                    id integer PRIMARY KEY,
                    campus text,
                    building text,
                    date text,
                    room text,
                    time text,
                    first_seen integer,
                    last_seen integer
                );
            """
        elif exposures_table == 'uwa_exposures':
            table_create = """
                CREATE TABLE IF NOT EXISTS uwa_exposures (
                    id integer PRIMARY KEY,
                    date text,
                    location text,
                    time text,
                    first_seen integer,
                    last_seen integer
                );
            """
        elif exposures_table == 'murdoch_exposures':
            table_create = """
                CREATE TABLE IF NOT EXISTS murdoch_exposures (
                    id integer PRIMARY KEY,
                    campus text,
                    date text,
                    location text,
                    time text,
                    first_seen integer,
                    last_seen integer
                );
            """
        elif exposures_table == 'curtin_exposures':
            table_create = """
                CREATE TABLE IF NOT EXISTS curtin_exposures (
                    id integer PRIMARY KEY,
                    campus text,
                    contact_type text,
                    date text,
                    location text,
                    time text,
                    first_seen integer,
                    last_seen integer
                );
            """
        
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
        for adminDestEmail in AdminDestAddr:

            message = f"""To: {AdminDestAddr}
From: {adminFromAddr}
Reply-To: {AdminReplyAddr}
Subject: {AdminSubjLine}

{errorMsg}.""".encode("ascii", "replace")

            try:
                with smtplib.SMTP(adminSmtpServ, adminSmtpPort) as server:
                    server.starttls()
                    server.sendmail(adminFromAddr, adminDestEmail, message)
                    server.ehlo()
                    server.login(adminSmtpUser, adminSmtpPass)

                    print(f"Email sent to {destEmail}")
            except smtplib.SMTPException as e:
                print("SMTP error occurred: " + str(e))
    else:
        print("Admin alerts disabled")
        print(errorMsg)

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


def chunky_alerts(text, delimeter="\n\n", max_length=1990):
    i = 0
    while i < len(text):
        # Note: if the last chunk is less than max_length, it will be included
        if i + max_length > len(text):
            yield text[i:]
            break

        nearest_delim = text[i:i+max_length][::-1].index(delimeter) # Calculate the nearest delimiter index, by reversing the string and finding the first occurence of the delimeter
        yield text[i:i+max_length-nearest_delim -len(delimeter)] # we don't need the additional delim chars here
        i += max_length - nearest_delim # we need them here, so we don't end up including a bunch of line breaks


def post_message_to_discord(text, blocks=None):

    for discord_webhook_url in discord_webhook_urls:

        # Discord doesn't let us post more than 2000 characters at a time
        # so we need to split and make individual posts every 2 seconds to avoid rate limits.
        # This may spam notifications depending on your server settings
        alert_total = len(list(chunky_alerts(text)))
        for alert_number, alert in enumerate(chunky_alerts(text)):
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


def html_cleanString(s):

    try:
        s = str(lxml.html.fromstring(s).text_content())
    except:
        pass

    s = s.strip().replace('\r','').replace('\n','').rstrip(',')

    return s

def wahealth_GetLocations():

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
        raise Exception("WAHealth Failed - Parsing page failure")

    if len(rows) < 1:
        print(f"found no data")
        raise Exception("table_parse_fail")

    return rows


def wahealth_cleanString(location):

    newLoc = ""
    location = location.replace("\xa0", "")
    for line in location.split("\n"):
        newLoc = newLoc + line.lstrip().rstrip() + ", "
    return newLoc.rstrip(", ").lstrip(", ").replace(", , ", "; ").replace(" , ", " ").rstrip("\r\n")


def wahealth_buildDetails(exposure):
    exposure_details = f"""Date and Time: {exposure['datentime']}
Suburb: {exposure['suburb']}
Location: {exposure['location']}
Updated: {exposure['updated']}
Advice: {exposure['advice']}\n\n"""
    
    return exposure_details

def wahealth_filterExposures(exposures):

    # examine each exposure
    # if it is in the DB already, get the id and update last seen
    # if it is not in the DB: create the first seen date and make id 'None'
    alerts = []
    for exposure in exposures:
        
        record = {}

        record['datentime'] = wahealth_cleanString(exposure[1].text_content())
        record['suburb'] = wahealth_cleanString(exposure[2].text_content())
        record['location'] = wahealth_cleanString(exposure[3].text_content())
        record['updated'] = wahealth_cleanString(exposure[4].text_content())
        record['advice'] = wahealth_cleanString(exposure[5].text_content())
        record['last_seen'] = unix_timestamp

        query = """SELECT count(id), coalesce(id, 0) FROM wahealth_exposures WHERE 
                    datentime = ? 
                    AND suburb = ?
                    AND location = ?
                    AND updated = ?
                    AND advice = ?;"""

        args = (record['datentime'], record['suburb'], record['location'], record['updated'], record['advice'])
        result = dbconn.execute(query, args)
        
        id = result.fetchone()
        if id[0] > 0:
            record['id'] = id[1]
        else:
            record['id'] = None
            record['first_seen'] = unix_timestamp
        
        alerts.append(record)

    return alerts


def sheet_GetLocations():

    # Consumer: https://docs.google.com/spreadsheets/d/1-U8Ea9o9bnST5pzckC8lzwNNK_jO6kIVUAi5Uu_-Ltc/edit?fbclid=IwAR3EaVvU0di14R6zqqfFP7sDLCwPOYax_SjMcDlmV2D2leqKGRAROCInpj4#gid=1427159313
    # Detailed/Admin: https://docs.google.com/spreadsheets/d/12fN17qFR8ruSk2yf29CR1S6xZMs_nve2ww_6FJk7__8/edit#gid=0

    sheet_id = "1-U8Ea9o9bnST5pzckC8lzwNNK_jO6kIVUAi5Uu_-Ltc"
    sheet_name = "All%20Locations"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

    res = requests.get(url)
    contents = codecs.decode(res.content, 'UTF-8')
    contents = contents.replace('"",','')
    split = contents.splitlines()
    reader = csv.reader(split)

    sheetExposures = []

    for record in reader:
        exposure = {}

        if record[4] == "Business":
            exposure['datentime'] = html_cleanString(record[2])
            exposure['suburb'] = html_cleanString(record[1])
            exposure['location'] = html_cleanString(record[0]) + " " + html_cleanString(record[3])
            exposure['last_seen'] = unix_timestamp

            query = """SELECT count(id), coalesce(id, 0) FROM sheet_exposures WHERE
                        datentime = ?
                        AND suburb = ?
                        AND location = ?;"""
            
            args = (exposure['datentime'], exposure['suburb'], exposure['location'])
            result = dbconn.execute(query, args)

            id = result.fetchone()
            if id[0] > 0:
                exposure['id'] = id[1]
            else:
                exposure['id'] = None
                exposure['first_seen'] = unix_timestamp

            sheetExposures.append(exposure)

    if(len(sheetExposures) < 1):
        raise Exception("Sheets Failed - Zero records retrieved")

    return sheetExposures



def sheet_buildDetails(exposure):
    exposure_details = f"""Date and Time: {exposure['datentime']}
Suburb: {exposure['suburb']}
Location: {exposure['location']}\n\n"""
    
    return exposure_details


def ecu_GetLocations():
    ecu_url = 'https://www.ecu.edu.au/covid-19/advice-for-staff'


    req = requests.get(ecu_url)

    if req.status_code != 200:
        print(f"Failed to fetch page: {req.reason}")
        raise Exception("reqest_not_ok")

    doc = lxml.html.fromstring(req.content)

    container = doc.xpath('//div[@id="accordion-01e803ff84807e270adaddf7ade2fa91035b560d"]')[0]
    tables = container.xpath(".//table")

    outRows = []


    for table in tables:
        campus = html_cleanString(table.getparent().getparent().getparent().getparent()[0].text_content().strip())
        rows = table.xpath('./tr')

        for row in rows:
            record = {}

            record['campus'] = campus
            record['date'] = html_cleanString(row[0].text_content().strip())
            record['time'] = html_cleanString(row[1].text_content().strip())
            record['building'] = html_cleanString(row[2].text_content().strip())
            record['room'] = html_cleanString(row[3].text_content().strip())
            record['last_seen'] = unix_timestamp

            query = """SELECT count(id), coalesce(id, 0) FROM ecu_exposures WHERE
                        campus = ?
                        AND date = ?
                        AND time = ?
                        AND building = ?
                        AND room = ?;"""
            
            args = (record['campus'], record['date'], record['time'], record['building'], record['room'])
            result = dbconn.execute(query, args)

            id = result.fetchone()
            if id[0] > 0:
                record['id'] = id[1]
            else:
                record['id'] = None
                record['first_seen'] = unix_timestamp

            outRows.append(record)

    for table in tables:
        header = table.xpath('.//thead')[0][0]

        if (header[0].text_content().strip() == 'Date' and
            header[1].text_content().strip() == 'Time' and
            header[2].text_content().strip() == 'Building' and
            header[3].text_content().strip() == 'Room'):
            pass
        else:
            raise Exception("ECU Failed - Parsing page failure")

    return outRows


def ecu_buildDetails(exposure):
    exposure_details = f"""Date: {exposure['date']}
Time: {exposure['time']}
Campus: {exposure['campus']}
Building: {exposure['building']}
Room: {exposure['room']}\n\n"""
    
    return exposure_details


def uwa_GetLocations():
    uwa_url = 'https://www.uwa.edu.au/covid-19-faq/Home'


    req = requests.get(uwa_url)

    if req.status_code != 200:
        print(f"Failed to fetch page: {req.reason}")
        raise Exception("reqest_not_ok")

    doc = lxml.html.fromstring(req.content)

    rows = doc.xpath('//div/table/tbody/tr')

    header = rows.pop(0)

    outRows = []

    for row in rows:
        record = {}

        record['date'] = html_cleanString(row[0].text_content().strip())
        record['location'] = html_cleanString(row[1].text_content().strip())
        record['time'] = html_cleanString(row[2].text_content().strip())
        record['last_seen'] = unix_timestamp

        query = """SELECT count(id), coalesce(id, 0) FROM uwa_exposures WHERE
                    date = ?
                    AND time = ?
                    AND location = ?;"""
        
        args = (record['date'], record['time'], record['location'])
        result = dbconn.execute(query, args)

        id = result.fetchone()
        if id[0] > 0:
            record['id'] = id[1]
        else:
            record['id'] = None
            record['first_seen'] = unix_timestamp

        outRows.append(record)


    if (header[0].text_content().strip() == 'Date' and
        header[1].text_content().strip() == 'Location' and
        header[2].text_content().strip() == 'Time'):
        pass
    else:
        raise Exception("UWA Failed - Parsing page failure")

    return outRows


def uwa_buildDetails(exposure):
    exposure_details = f"""Date: {exposure['date']}
Time: {exposure['time']}
Location: {exposure['location']}\n\n"""
    
    return exposure_details


def murdoch_GetLocations():
    murdoch_url = 'https://www.murdoch.edu.au/notices/covid-19-advice'


    req = requests.get(murdoch_url)

    if req.status_code != 200:
        print(f"Failed to fetch page: {req.reason}")
        raise Exception("reqest_not_ok")

    doc = lxml.html.fromstring(req.content)

    rows = doc.xpath('//tr')

    header = rows.pop(0)

    outRows = []

    for row in rows:
        record = {}

        record['date'] = html_cleanString(row[0].text_content().strip())
        record['time'] = html_cleanString(row[1].text_content().strip())
        record['campus'] = html_cleanString(row[2].text_content().strip())
        record['location'] = html_cleanString(row[3].text_content().strip())
        record['last_seen'] = unix_timestamp

        query = """SELECT count(id), coalesce(id, 0) FROM murdoch_exposures WHERE
                    date = ?
                    AND time = ?
                    AND campus = ?
                    AND location = ?;"""
        
        args = (record['date'], record['time'], record['campus'], record['location'])
        result = dbconn.execute(query, args)

        id = result.fetchone()
        if id[0] > 0:
            record['id'] = id[1]
        else:
            record['id'] = None
            record['first_seen'] = unix_timestamp

        outRows.append(record)


    if (header[0].text_content().strip() == 'Date' and
        header[1].text_content().strip() == 'Time' and
        header[2].text_content().strip() == 'Campus' and 
        header[3].text_content().strip() == 'Location'):

        pass
    else:
        raise Exception("Murdoch Failed - Parsing page failure")

    return outRows


def murdoch_buildDetails(exposure):
    exposure_details = f"""Date: {exposure['date']}
Time: {exposure['time']}
Campus: {exposure['campus']}
Location: {exposure['location']}\n\n"""
    
    return exposure_details


def curtin_GetLocations():
    curtin_url = 'https://www.curtin.edu.au/novel-coronavirus/recent-exposure-sites-on-campus/'


    req = requests.get(curtin_url)

    if req.status_code != 200:
        print(f"Failed to fetch page: {req.reason}")
        raise Exception("reqest_not_ok")

    doc = lxml.html.fromstring(req.content)

    table = doc.xpath('//table[@id="table_1"]')[0]
    rows = table.xpath('.//tr')

    header = rows.pop(0)

    outRows = []

    for row in rows:
        record = {}

        record['date'] = html_cleanString(row[0].text_content().strip())
        record['time'] = html_cleanString(row[1].text_content().strip())
        record['campus'] = html_cleanString(row[2].text_content().strip())
        record['location'] = html_cleanString(row[3].text_content().strip())
        record['contact_type'] = html_cleanString(row[4].text_content().strip())
        record['last_seen'] = unix_timestamp

        query = """SELECT count(id), coalesce(id, 0) FROM curtin_exposures WHERE
                    date = ?
                    AND time = ?
                    AND campus = ?
                    AND location = ?
                    AND contact_type = ?;"""
        
        args = (record['date'], record['time'], record['campus'], record['location'], record['contact_type'])
        result = dbconn.execute(query, args)

        id = result.fetchone()
        if id[0] > 0:
            record['id'] = id[1]
        else:
            record['id'] = None
            record['first_seen'] = unix_timestamp

        outRows.append(record)


    if (header[0].text_content().strip() == 'Date' and
        header[1].text_content().strip() == 'Time' and
        header[2].text_content().strip() == 'Campus' and 
        header[3].text_content().strip() == 'Location' and 
        header[4].text_content().strip() == 'Contact type'):

        pass
    else:
        raise Exception("Curtin Failed - Parsing page failure")

    return outRows


def curtin_buildDetails(exposure):
    exposure_details = f"""Date: {exposure['date']}
Time: {exposure['time']}
Campus: {exposure['campus']}
Location: {exposure['location']}
Contact Type: {exposure['contact_type']}\n\n"""
    
    return exposure_details



# load sqlite3
dbconn = create_connection(db_file)

# backup db incase things go bad
shutil.copy(db_file, f"{db_file}.bak")



# get exposures
try:
    wahealth_exposures = wahealth_GetLocations()
    #sheet_exposures = sheet_GetLocations()
    sheet_exposures = []
    ecu_exposures = ecu_GetLocations()
    uwa_exposures = uwa_GetLocations()
    curtin_exposures = curtin_GetLocations()
    murdoch_exposures = murdoch_GetLocations()
except Exception as e:
    print(e)
    traceback.print_stack()
    sendAdminAlert("Unable to fetch data, please investigate")
    exit()

# clean exposures list and check if they've already been seen
wahealth_alerts = wahealth_filterExposures(wahealth_exposures)

# for each new exposure add it to the DB and add it to a string for comms

wahealth_comms = ""
sheet_comms = ""
ecu_comms = ""
uwa_comms = ""
murdoch_comms = ""
curtin_comms = ""


for exposure in wahealth_alerts:

    if exposure['id'] is None:
        wahealth_comms = wahealth_comms + wahealth_buildDetails(exposure)

        query = f"""INSERT INTO wahealth_exposures (datentime, suburb, location, updated, advice, first_seen, last_seen) 
                    VALUES (?,?,?,?,?,?,?) """

        args = (exposure['datentime'], exposure['suburb'], exposure['location'], exposure['updated'], exposure['advice'], exposure['first_seen'], exposure['last_seen'])
        result = dbconn.execute(query, args)
    
    else:
        query = f"""UPDATE wahealth_exposures SET last_seen = ? 
                    WHERE id = ? """

        args = (exposure['last_seen'], exposure['id'])
        result = dbconn.execute(query, args)

    #if debug and len(wahealth_comms) > 0:
    #    print(wahealth_comms)

for exposure in sheet_exposures:

    if exposure['id'] is None:
        sheet_comms = sheet_comms + sheet_buildDetails(exposure)

        query = f"""INSERT INTO sheet_exposures (datentime, suburb, location, first_seen, last_seen) 
                    VALUES (?,?,?,?,?) """

        args = (exposure['datentime'], exposure['suburb'], exposure['location'], exposure['first_seen'], exposure['last_seen'])
        result = dbconn.execute(query, args)
    
    else:
        query = f"""UPDATE sheet_exposures SET last_seen = ? 
                    WHERE id = ? """

        args = (exposure['last_seen'], exposure['id'])
        result = dbconn.execute(query, args)

    #if debug and len(sheet_comms) > 0:
    #    print(sheet_comms)

for exposure in ecu_exposures:

    if exposure['id'] is None:
        ecu_comms = ecu_comms + ecu_buildDetails(exposure)

        query = f"""INSERT INTO ecu_exposures (date, time, campus, building, room, first_seen, last_seen) 
                    VALUES (?,?,?,?,?,?,?) """

        args = (exposure['date'], exposure['time'], exposure['campus'], exposure['building'], exposure['room'], exposure['first_seen'], exposure['last_seen'])
        result = dbconn.execute(query, args)
    
    else:
        query = f"""UPDATE ecu_exposures SET last_seen = ? 
                    WHERE id = ? """

        args = (exposure['last_seen'], exposure['id'])
        result = dbconn.execute(query, args)

    #if debug and len(ecu_comms) > 0:
    #    print(ecu_comms)

for exposure in uwa_exposures:

    if exposure['id'] is None:
        uwa_comms = uwa_comms + uwa_buildDetails(exposure)

        query = f"""INSERT INTO uwa_exposures (date, time, location, first_seen, last_seen) 
                    VALUES (?,?,?,?,?) """

        args = (exposure['date'], exposure['time'], exposure['location'], exposure['first_seen'], exposure['last_seen'])
        result = dbconn.execute(query, args)
    
    else:
        query = f"""UPDATE uwa_exposures SET last_seen = ? 
                    WHERE id = ? """

        args = (exposure['last_seen'], exposure['id'])
        result = dbconn.execute(query, args)

    #if debug and len(uwa_comms) > 0:
    #    print(uwa_comms)

for exposure in murdoch_exposures:

    if exposure['id'] is None:
        murdoch_comms = murdoch_comms + murdoch_buildDetails(exposure)

        query = f"""INSERT INTO murdoch_exposures (date, time, campus, location, first_seen, last_seen) 
                    VALUES (?,?,?,?,?,?) """

        args = (exposure['date'], exposure['time'], exposure['campus'], exposure['location'], exposure['first_seen'], exposure['last_seen'])
        result = dbconn.execute(query, args)
    
    else:
        query = f"""UPDATE murdoch_exposures SET last_seen = ? 
                    WHERE id = ? """

        args = (exposure['last_seen'], exposure['id'])
        result = dbconn.execute(query, args)

    #if debug and len(murdoch_comms) > 0:
    #    print(murdoch_comms)

for exposure in curtin_exposures:

    if exposure['id'] is None:
        curtin_comms = curtin_comms + curtin_buildDetails(exposure)

        query = f"""INSERT INTO curtin_exposures (date, time, campus, location, contact_type, first_seen, last_seen) 
                    VALUES (?,?,?,?,?,?,?) """

        args = (exposure['date'], exposure['time'], exposure['campus'], exposure['location'], exposure['contact_type'], exposure['first_seen'], exposure['last_seen'])
        result = dbconn.execute(query, args)
    
    else:
        query = f"""UPDATE curtin_exposures SET last_seen = ? 
                    WHERE id = ? """

        args = (exposure['last_seen'], exposure['id'])
        result = dbconn.execute(query, args)

    #if debug and len(curtin_comms) > 0:
    #    print(curtin_comms)


# Build report

comms = ""

if(len(wahealth_comms) > 0):
    comms = comms + "*WA Health Exposure Sites*\n\n" + wahealth_comms + "\n\n"

if(len(sheet_comms) > 0):
    comms = comms + "*Unofficial Civilian Compiled Exposure Sites*\n\n" + sheet_comms + "\n\n"

if(len(ecu_comms) > 0):
    comms = comms + "*Edith Cowan University Exposure Sites*\n\n" + ecu_comms + "\n\n"

if(len(uwa_comms) > 0):
    comms = comms + "*University of Western Australia Exposure Sites*\n\n" + uwa_comms + "\n\n"

if(len(murdoch_comms) > 0):
    comms = comms + "*Murdoch University Exposure Sites*\n\n" + murdoch_comms + "\n\n"

if(len(curtin_comms) > 0):
    comms = comms + "*Curtin University Exposure Sites*\n\n" + curtin_comms + "\n\n"

if debug and len(comms) > 0:
    print(comms)

# kludge ugh
mailPostSuccess = 200
if not debug:
 if len(comms) > 0 and dreamhostAnounces:
     mailPostSuccess = sendDhAnnounce(comms)
 if len(comms) > 0 and emailAlerts:
     sendEmails(comms)
 if len(comms) > 0 and slackAlerts:
     post_message_to_slack(comms)
 if len(comms) > 0 and discordAlerts:
     post_message_to_discord(comms)

dbconn.commit()

# we don't close as we're using autocommit, this results in greater 
# compatability with different versions of sqlite3

if len(comms) > 0 and dreamhostAnounces and mailPostSuccess != 200 and not debug:
 print(result)
 os.replace(f"{db_file}.bak", db_file)
 sendAdminAlert("Unable to send mail, please investigate")
else:
 os.remove(f"{db_file}.bak")
