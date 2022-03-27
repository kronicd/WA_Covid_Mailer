# WA Covid Mailer

Collects WA Covid-19 Exposure Locations from:

* [Healthy WA's Covid19 Exposure Locations](https://www.healthywa.wa.gov.au/COVID19locations)
* [Unofficial Civilian Compiled Exposure Sites](https://docs.google.com/spreadsheets/d/1-U8Ea9o9bnST5pzckC8lzwNNK_jO6kIVUAi5Uu_-Ltc/htmlview?pru=AAABfzYp9xU*O5BeDYIVxSR9HGqWRuiLNQ) - [Contribute Here](https://www.facebook.com/groups/708242463497733)
* [Edith Cowan University](https://www.ecu.edu.au/covid-19/advice-for-staff)
* [University of Western Australia](https://www.uwa.edu.au/covid-19-faq/Home)
* [Murdoch University](https://www.murdoch.edu.au/notices/covid-19-advice)
* ~~[Curtin University](https://www.curtin.edu.au/novel-coronavirus/recent-exposure-sites-on-campus/)~~ (while code exists for Curtin University they have since removed exposure data from their website. The code hasn't been removed in case they put it back but currently it does not work)

and sends them to Discord and adds them to a database.

`exposure_parser.py` can be imported to collect exposures for other purposes. Similarly, `exposures.py` contains classes for locations and exposures

## Setup

### Edit the configuration file `config.json`

~~~json
{
    "database_path": "/path/to/database.db",
    "discord_webhooks": [
        "https://discordapp.com/api/webhooks/XXXXXXX/XXXXXXX"
    ]
}
~~~

### Installing dependencies

This project depends on a few libraries that can be installed with
~~~
pip3 install requests lxml sqlite3 pytz geopy
~~~

### Setup a cronjob

To run this script at intervals you can use a cronjob if you are running Linux; for example, this will run the script every fifteen minutes:
~~~
*/15 * * * * /usr/bin/python3 /path/to/discord_notify.py > /dev/null 2>&1
~~~

## Credits

This project is based on [another project by user kronicd](https://github.com/kronicd/WA_Covid_Mailer). I cloned their code but cut down and rewrote most of it in order to properly parse the data from the exposure sources.

## License

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg
