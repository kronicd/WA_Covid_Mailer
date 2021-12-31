# WA Covid Mailer

Sends alerts from [Healthy WA's Covid19 Exposure Locations](https://www.healthywa.wa.gov.au/COVID19locations) to via email and slack.

## Setup

### Edit the configuration items in wacovidmailer.py

~~~
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
~~~

### Install your deps

~~~
pip3 install requests lxml sqlite3
~~~

### Setup your cronjob

~~~
*/30 * * * * /usr/bin/python3 /path/to/wacovidmailer.py > /dev/null 2>&1
~~~

## License

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg