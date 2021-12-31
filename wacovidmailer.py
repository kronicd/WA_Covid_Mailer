#!/usr/bin/env python3


import requests
import lxml.html
import sqlite3
import json
from pprint import pprint
import smtplib, ssl
from datetime import datetime


waGovUrl = "https://www.healthywa.wa.gov.au/COVID19locations"
date_time = datetime.now().strftime("%m/%d/%Y %H:%M:%S")


### CONFIGURATION ITEMS ###

# Debug mode disables sending of alerts
debug = False

# Database location
db_file = "/path/to/exposures.db" # will be created on first use

# Email details
emailAlerts = True
smtpServ = ""
smtpPort = ""
fromAddr = ""
replyAddr = ""
destAddr = ["email1@example.com", "email2@example.com"]
subjLine = f"Alert: Updated WA covid-19 exposure sites ({date_time})"

# Slack Alerts
slackAlerts = True
webhook_urls = ["https://hooks.slack.com/services/XXXXXXX/XXXXXXX/XXXXXXX"] # slack webhook 1
webhook_urls = webhook_urls + ["https://hooks.slack.com/services/XXXXXXX/XXXXXXX/XXXXXXX"] # slack webhook 2

### END OF CONFIGURATION ITEMS


if debug:
    db_file = "exposures.db"


def create_connection(db_file):

    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(f'something went wrong: {e}')

    # create tables if needed
    query = "SELECT count(name) FROM sqlite_master WHERE type='table' AND name='exposures';"

    result = conn.execute(query)

    if result.fetchone()[0]==1:
        pass
    else:
        print("creating table...")
        table_create =  """ CREATE TABLE IF NOT EXISTS exposures (
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


{body}.""".encode('ascii', 'replace')
        print(message)

        try:
            context = ssl.create_default_context()

            with smtplib.SMTP_SSL(smtpServ, smtpPort, context=context) as server:
                server.sendmail(fromAddr, destEmail, message)
            print('Email sent')
        except smtplib.SMTPException as e:
            print('SMTP error occurred: ' + str(e))

def post_message_to_slack(text, blocks = None):

    for webhook_url in webhook_urls:
        slack_data = {'text': text}

        response = requests.post(
            webhook_url, data=json.dumps(slack_data),
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code != 200:
            raise ValueError(
                'Request to slack returned an error %s, the response is:\n%s'
                % (response.status_code, response.text))

        print("Slack sent")


def getDetails():

    req = requests.get(waGovUrl)

    if req.status_code != 200:
        print(f'Failed to fetch page: {req.reason}')
        raise Exception('reqest_not_ok')

    doc = lxml.html.fromstring(req.content)
    
    sites_table = doc.xpath('//table[@id="locationTable"]')[0][1]
    rows = sites_table.xpath('.//tr')

    if len(rows) < 1:
        print(f'found no data')
        raise Exception('table_parse_fail')

    return rows

def cleanString(location):

    newLoc = ""
    location = location.replace("\xa0","")
    for line in location.split('\n'):
        newLoc = (newLoc + line.lstrip().rstrip() + ", ")
    return newLoc.rstrip(', ').replace(', , ',', ').rstrip("\r\n")

def buildDetails(exposure):
    datentime = cleanString(exposure[1].text_content())
    suburb = cleanString(exposure[2].text_content())
    location = cleanString(exposure[3].text_content())
    updated = cleanString(exposure[4].text_content())
    advice = cleanString(exposure[5].text_content())

    exposure_details =  f"""Date and Time: {datentime}
Suburb: {suburb}
Location: {location}
Updated: {updated}
Advice: {advice}\n\n"""

    exposure_details = exposure_details.rstrip("\r\n") + "\n\n"

    return exposure_details

# load sqlite3
conn = create_connection(db_file)

# get exposures
exposures = getDetails()

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
    result = conn.execute(query,args)

    if result.fetchone()[0] > 0:
        pass
        #print('exposure exists')
    else:
        alerts.append(exposure)

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
    result = conn.execute(query,args)
    
    if debug:
        print(comms)

if not debug:

    if len(comms) > 0 and emailAlerts:
        sendEmails(comms)

    if len(comms) > 0 and slackAlerts:
        post_message_to_slack(comms)


conn.commit()
conn.close()




