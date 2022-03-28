# WA Covid Exposure Tracker

Collects WA Covid-19 Exposure Locations from:

* [Healthy WA's COVID-19 Exposure Locations](https://www.healthywa.wa.gov.au/COVID19locations)
* [Unofficial Civilian Compiled Exposure Sites](https://docs.google.com/spreadsheets/d/1-U8Ea9o9bnST5pzckC8lzwNNK_jO6kIVUAi5Uu_-Ltc/htmlview?pru=AAABfzYp9xU*O5BeDYIVxSR9HGqWRuiLNQ) - [Contribute Here](https://www.facebook.com/groups/708242463497733)
* [Edith Cowan University](https://www.ecu.edu.au/covid-19/advice-for-staff)
* [University of Western Australia](https://www.uwa.edu.au/covid-19-faq/Home)
* [Murdoch University](https://www.murdoch.edu.au/notices/covid-19-advice)
* ~~[Curtin University](https://www.curtin.edu.au/novel-coronavirus/recent-exposure-sites-on-campus/)~~ (while code exists for Curtin University they have since removed exposure data from their website. The code hasn't been removed in case they put it back but currently it does not work)

and sends them to Discord and adds them to a database.

`exposure_parser.py` can be imported to collect exposures for other purposes. Similarly, `exposure_tools.py` contains classes for locations and exposures

## Setup

### Edit the configuration file `config.json`

~~~json
{
    "database_file": "/path/to/database.db",
    "discord_webhooks": [
        "https://discordapp.com/api/webhooks/XXXXXXX/XXXXXXX"
    ]
}
~~~

### Installing dependencies

This project depends on a few libraries that can be installed with
~~~
pip3 install requests lxml pytz geopy
~~~

### Setup a cronjob

To run this script at intervals you can use a cronjob if you are running Linux; for example, this will run the script every fifteen minutes:
~~~
*/15 * * * * /usr/bin/python3 /path/to/discord_notify.py > /dev/null 2>&1
~~~

## Using `exposure_parser.py`

### Basic Usage
If you plan to use this project as a library, you can import `exposure_parser.py` like so:
```python
import exposure_parser

LAST_RUN = # (Read this from a file if you're using it)

# Get exposures from the sources you need
exposures = \
    exposure_parser.murdoch_exposures()             + \
    exposure_parser.uwa_exposures()                 + \
    exposure_parser.ecu_exposures()                 + \
    exposure_parser.civilian_exposures(True)        + \
    exposure_parser.wahealth_exposures(LAST_RUN)

# (Process exposure data)
```

### Optimisation

Because geocoding can be a very time consuming process, there are some workarounds implemented to prevent the data which has already been processed from being processed again:
* The (`since`)[## "`datetime.datetime`, `datetime.date`, or ISO-formatted date string"] parameter in `exposure_parser.wahealth_exposures` gets all exposures since the date specified, so if this date is set to the last time the program was run it is possible to only get exposures from that day or later
* The `get_new` and `keep_hash_list` parameters in `exposure_parser.civilian_exposures`: the former checks every new exposure it reads against a list of hashes of all the previous exposures that still exist in the source and the latter allows this list to be kept
While the module works without these, it is highly recommended that you use them and store all new exposures in a database so that you don't have to process all the locations every time you run your program.

## Credits

This project is based on [another project by user kronicd](https://github.com/kronicd/WA_Covid_Mailer). I cloned their code but cut down and rewrote most of it in order to properly parse the data from the exposure sources.

## License

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg
