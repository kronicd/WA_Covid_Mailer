# WA Covid Mailer

Sends alerts from [Healthy WA's Covid19 Exposure Locations](https://www.healthywa.wa.gov.au/COVID19locations) to via email, slack, and [dreamhost announce](https://help.dreamhost.com/hc/en-us/articles/215683497-How-do-I-configure-and-manage-an-Announcement-List-) lists.

## Setup

### Edit the configuration items in wacovidmailer.py

~~~python
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

# Dreamhost Announce
dreamhostAnounces = False
apiKey = ""
listDomain = ""
listName = ""
subjLine = f"Alert: Updated WA covid-19 exposure sites ({date_time})"

### END OF CONFIGURATION ITEMS
~~~

### Install your deps

~~~
pip3 install requests lxml sqlite3 pytz
~~~

### Setup your cronjob

~~~
*/15 * * * * /usr/bin/python3 /path/to/wacovidmailer.py > /dev/null 2>&1
~~~

## Notes on exposures.kronicd.net

An instance of the code is running and is available at https://exposures.kronicd.net, which is configured as follows:

* Custom PHP is used to add and remove email addresses from a dreamhost announcement mailing list
* `wacovidmailer.py` is configured to run every 15 minutes and has the `Dreamhost Announce` configuration items filled out
* Dreamhost manages the mailing list functionality including confirmation emails for subscribe actions
* The PHP code is not included as part of this release as it would be of limited use and add significant confusion for those attempting deployment

The core of the subscription function is essentially:

~~~php
if($invalid == False) {
    $format = 'https://api.dreamhost.com/?key=%s&cmd=announcement_list-add_subscriber&listname=LISTNAME&domain=DOMAIN&email=%s';
    $subUrl = sprintf($format, $apiKey, $email);
    file_get_contents($subUrl);
    $msg = "You have been subscribed to the mailing list. Please check your email for a confirmation link, you may need to check your spam folder.";
} else {
    $msg = "Email address invalid or not supplied.";

}
~~~

## License

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg
