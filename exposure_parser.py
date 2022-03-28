#!/usr/bin/env python3

from dataclasses import dataclass
from functools import partial
import datetime as dt
import hashlib
import os
from typing import List, Union
import lxml.html
import requests
import codecs
import csv

import exposure_tools

NOW = dt.datetime.now()

def html_clean_string(s):
    try:
        s = str(lxml.html.fromstring(s).text_content())
    except:
        pass
    s = s.strip().replace('\r','').replace('\n','').rstrip(',')
    return s

def wahealth_exposures(since: Union[dt.datetime, dt.date, str] = None) -> List[exposure_tools.Exposure]:
    since_type = type(since)
    if since == None:
        since_date = None
    elif since_type == dt.datetime:
        since_date = since.date()
    elif since_type == str:
        since_date = dt.datetime.fromisoformat(since)
    else:
        raise TypeError("Parameter 'since' can only be of type datetime.datetime, datetime.date, or and ISO-formatted string.")
    
    req = requests.get("https://www.healthywa.wa.gov.au/COVID19locations")
    if req.status_code != 200:
        raise Exception(f"Failed to get HealthyWA exposure sheet ({req.reason})")

    doc = lxml.html.fromstring(req.content)

    sites_table = doc.xpath('//table[@id="locationTable"]')[0][1]
    rows = sites_table.xpath(".//tr")

    # check for proper header
    header = doc.xpath('//table[@id="locationTable"]')[0][0]
    headerRows = header.xpath(".//th")

    healthywa_parsing_error = "Failed to parse ECU exposure list"
    assert headerRows[0].text_content() == 'Exposure date & time', healthywa_parsing_error
    assert headerRows[1].text_content() == 'Suburb', healthywa_parsing_error
    assert headerRows[2].text_content() == 'Location', healthywa_parsing_error
    assert headerRows[3].text_content() == 'Date updated', healthywa_parsing_error
    assert headerRows[4].text_content() == 'Health advice', healthywa_parsing_error

    if len(rows) < 1:
        raise Exception("HealthyWA exposure sheet failed; no records were found.")

    exposures = []

    for row in rows:
        updated = dt.datetime.strptime(row[4].text_content(), "%d/%m/%Y")
        if since_date:
            if updated.date() < since_date:
                continue  # If this entry hasn't been updated since the last run then it contains no new information and we can skip it
        date_time_str = _wahealth_clean_string(row[1].text_content())
        address = _wahealth_clean_string(row[3].text_content()) + ", " + _wahealth_clean_string(row[2].text_content())
        advice = _wahealth_clean_string(row[5].text_content())
        for expose_date in date_time_str.split(";"):
            expose_date = expose_date.strip()
            if expose_date.count("/") == 4:
                start_str, end_str = expose_date.replace(",", "").split("to")
                start_str = " ".join(start_str.strip().split(" ")[1:]).replace(" (midnight)", "")
                end_str = end_str.strip()
                start_datetime = dt.datetime.strptime(start_str, "%d/%m/%Y %I:%M%p")
                if end_str[0] in "123456789":
                    end_time_str, _, end_date_str = end_str.replace(" (midnight)", "").split(" ")
                    end_date = dt.datetime.strptime(end_date_str, "%d/%m/%Y")
                    end_time = dt.datetime.strptime(end_time_str, "%I:%M%p")
                    end_datetime = dt.datetime.combine(end_date, end_time.time())
                else:
                    end_str = " ".join(end_str.strip().split(" ")[1:]).replace(" (midnight)", "")
                    end_datetime = dt.datetime.strptime(end_str, "%d/%m/%Y %I:%M%p")
            else:
                str_date, str_time = expose_date.split(", ")
                date = dt.datetime.strptime(str_date.split(" ")[1], "%d/%m/%Y")
                str_time_start, str_time_end = str_time.split(" to ")
                start_time = dt.datetime.strptime(str_time_start, "%I:%M%p")
                end_time = dt.datetime.strptime(str_time_end, "%I:%M%p")
                start_datetime = dt.datetime.combine(date, start_time.time())
                end_datetime = dt.datetime.combine(date, end_time.time())

            exposure = exposure_tools.Exposure(start_datetime, address, None, end_datetime, advice)
            exposures.append(exposure)

    return exposures


def _wahealth_clean_string(location):
    new_loc = ""
    location = location.replace("\xa0", "")
    for line in location.split("\n"):
        new_loc = new_loc + line.lstrip().rstrip() + ", "
    return new_loc.rstrip(", ").lstrip(", ").replace(", , ", "; ").replace(" , ", " ").rstrip("\r\n")


def civilian_exposures(get_new: bool = False, keep_hash_list: bool = True) -> List[exposure_tools.Exposure]:
    
    keep_hash_list |= get_new

    # Consumer: https://docs.google.com/spreadsheets/d/1-U8Ea9o9bnST5pzckC8lzwNNK_jO6kIVUAi5Uu_-Ltc/edit?fbclid=IwAR3EaVvU0di14R6zqqfFP7sDLCwPOYax_SjMcDlmV2D2leqKGRAROCInpj4#gid=1427159313
    # Detailed/Admin: https://docs.google.com/spreadsheets/d/12fN17qFR8ruSk2yf29CR1S6xZMs_nve2ww_6FJk7__8/edit#gid=0

    sheet_id = "1-U8Ea9o9bnST5pzckC8lzwNNK_jO6kIVUAi5Uu_-Ltc"
    sheet_name = "All%20Locations"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

    req = requests.get(url)
    if req.status_code != 200:
        raise Exception(f"Failed to get civilian-created exposure sheet ({req.reason})")
    contents = codecs.decode(req.content, 'UTF-8')
    contents = contents.replace('"",','')
    split = contents.splitlines()
    reader = csv.reader(split)

    civilian_hash_path = ".civilian_hashes.bin"
    civilian_hashes = []
    new_hashes = []

    if os.path.exists(civilian_hash_path):
        with open(civilian_hash_path, "rb") as f:
            for chunk in iter(partial(f.read, 16), b''):
                civilian_hashes.append(chunk)

    exposures = []

    for record in reader:
        if record[4] == "Business" or record[4] == "Government":
            address = html_clean_string(record[3])
            str_datetime = html_clean_string(record[2])
            if keep_hash_list:
                exposure_hash = hashlib.md5((address + str_datetime).encode()).digest()
                new_hashes.append(exposure_hash)
                if exposure_hash in civilian_hashes and get_new:
                    continue
            if "times unknown" in str_datetime:
                date = dt.datetime.strptime(str_datetime, "%d/%m/%Y times unknown")
                start_time = dt.time()
                end_time = dt.time()
            else:
                str_date, str_time = str_datetime.replace(" from ", " approximately ").split(" approximately ")
                date = dt.datetime.strptime(str_date, "%d/%m/%Y")
                str_time_start, str_time_end = str_time.split(" to ")
                start_time = dt.datetime.strptime(str_time_start, "%I:%M %p").time()
                end_time = dt.datetime.strptime(str_time_end, "%I:%M %p").time()

            exposure = exposure_tools.Exposure(dt.datetime.combine(date, start_time), address, record[0], dt.datetime.combine(date, end_time))
            exposures.append(exposure)

    with open(civilian_hash_path, "wb+") as f:
        for h in new_hashes:
            f.write(h)

    return exposures


def ecu_exposures() -> List[exposure_tools.Exposure]:
    req = requests.get("https://www.ecu.edu.au/covid-19/advice-for-staff")
    if req.status_code != 200:
        raise Exception(f"Failed to get ECU exposure list ({req.reason})")

    doc = lxml.html.fromstring(req.content)

    container = doc.xpath('//div[@id="accordion-01e803ff84807e270adaddf7ade2fa91035b560d"]')[0]
    tables = container.xpath(".//table")

    for table in tables:
        header = table.xpath('.//thead')[0][0]
        ecu_parsing_error = "Failed to parse ECU exposure list."
        assert header[0].text_content().strip() == 'Date', ecu_parsing_error
        assert header[1].text_content().strip() == 'Time', ecu_parsing_error
        assert header[2].text_content().strip() == 'Building', ecu_parsing_error
        assert header[3].text_content().strip() == 'Room', ecu_parsing_error

    campuses = {
        "Joondalup Campus": exposure_tools.reverse_geocode(-31.7524902, 115.7705912),
        "Mount Lawley Campus": exposure_tools.reverse_geocode(-31.9193013,115.8678213),
        "South West Campus": exposure_tools.reverse_geocode(-33.3667207,115.6508871)
    }
    exposures = []

    for table in tables:
        campus = html_clean_string(table.getparent().getparent().getparent().getparent()[0].text_content().strip())
        rows = table.xpath('./tr')

        for row in rows:
            str_date = html_clean_string(row[0].text_content().strip())
            str_time = html_clean_string(row[1].text_content().strip())
            building = html_clean_string(row[2].text_content().strip())
            room = html_clean_string(row[3].text_content().strip())

            date = dt.datetime.strptime(str_date, "%d/%m/%Y")
            str_time_start, str_time_end = str_time.split(" - ")
            start_time = dt.datetime.strptime(str_time_start, "%I:%M %p")
            end_time = dt.datetime.strptime(str_time_end, "%I:%M %p")

            exposure = exposure_tools.Exposure(dt.datetime.combine(date, start_time.time()), campuses[campus], room + ", " + building, dt.datetime.combine(date, end_time.time()))
            exposures.append(exposure)

    return exposures


def uwa_exposures() -> List[exposure_tools.Exposure]:
    req = requests.get("https://www.uwa.edu.au/covid-19-faq/Home")
    if req.status_code != 200:
        raise Exception(f"Failed to get UWA exposure list ({req.reason})")

    doc = lxml.html.fromstring(req.content)

    rows = doc.xpath('//div/table/tbody/tr')

    header = rows.pop(0)
    uwa_parsing_error = "Failed to parse UWA exposure list."
    assert header[0].text_content().strip() == 'Date', uwa_parsing_error
    assert header[1].text_content().strip() == 'Location', uwa_parsing_error
    assert header[2].text_content().strip() == 'Time', uwa_parsing_error

    address = exposure_tools.reverse_geocode(-31.9789061, 115.8158834)
    exposures = []

    for row in rows:
        if len(row) <= 0:
            continue
        str_date = html_clean_string(row[0].text_content().strip())
        location = html_clean_string(row[1].text_content().strip())
        str_time = html_clean_string(row[2].text_content().strip())

        date = dt.datetime.strptime(str_date, "%d %B").replace(year=NOW.year)
        str_time_start, str_time_end = str_time.replace("midnight", "12.00am").replace(":", ".").split("-")
        str_time_start = str_time_start.strip()
        str_time_end = str_time_end.strip()
        if str_time_start[-1] != "m":
            str_time_start += str_time_end[-2:]
        if "." not in str_time_start:
            str_time_start = str_time_start[:-2] + ".00" + str_time_start[-2:]
        if "." not in str_time_end:
            str_time_end = str_time_end[:-2] + ".00" + str_time_end[-2:]
        start_time = dt.datetime.strptime(str_time_start, "%I.%M%p")
        end_time = dt.datetime.strptime(str_time_end, "%I.%M%p")

        exposure = exposure_tools.Exposure(dt.datetime.combine(date, start_time.time()), address, location, dt.datetime.combine(date, end_time.time()))
        exposures.append(exposure)

    return exposures

# EXPOSURE TABLE REMOVED
def curtin_exposures() -> List[exposure_tools.Exposure]:
    req = requests.get("https://www.curtin.edu.au/novel-coronavirus/recent-exposure-sites-on-campus/")
    if req.status_code != 200:
        raise Exception(f"Failed to get Curtin University exposure list ({req.reason})")

    doc = lxml.html.fromstring(req.content)

    table = doc.xpath('//table[@id="table_1"]')[0]
    rows = table.xpath('.//tr')

    header = rows.pop(0)
    curtin_parsing_error = "Failed to parse Curtin University exposure list."
    assert header[0].text_content().strip() == 'Date', curtin_parsing_error
    assert header[1].text_content().strip() == 'Time', curtin_parsing_error
    assert header[2].text_content().strip() == 'Campus', curtin_parsing_error
    assert header[3].text_content().strip() == 'Location', curtin_parsing_error
    assert header[4].text_content().strip() == 'Contact type', curtin_parsing_error

    campuses = {
        "Bentley": exposure_tools.reverse_geocode(-32.0061905, 115.8922242),
        "": exposure_tools.reverse_geocode(-31.9544054, 115.852636)
    }
    exposures = []

    for row in rows:
        str_date = html_clean_string(row[0].text_content().strip())
        str_time = html_clean_string(row[1].text_content().strip())
        campus = html_clean_string(row[2].text_content().strip())
        location = html_clean_string(row[3].text_content().strip())
        advice = html_clean_string(row[4].text_content().strip())

        date = dt.datetime.strptime(str_date, "%d/%m/%Y")
        str_time_start, str_time_end = str_time.split("-")
        start_time = dt.datetime.strptime(str_time_start, "%I:%M%p")
        end_time = dt.datetime.strptime(str_time_end, "%I:%M %p")

        exposure = exposure_tools.Exposure(dt.datetime.combine(date, start_time.time()), campuses[campus], location, dt.datetime.combine(date, end_time.time()), advice)
        exposures.append(exposure)

    return exposures


def murdoch_exposures() -> List[exposure_tools.Exposure]:
    req = requests.get("https://www.murdoch.edu.au/notices/covid-19-advice")
    if req.status_code != 200:
        raise Exception(f"Failed to get Murdoch exposure list ({req.reason})")

    doc = lxml.html.fromstring(req.content)

    rows = doc.xpath('//tr')

    header = rows.pop(0)
    murdoch_parsing_error = "Failed to parse Murdoch University exposure list."
    assert header[0].text_content().strip() == 'Date', murdoch_parsing_error
    assert header[1].text_content().strip() == 'Time', murdoch_parsing_error
    assert header[2].text_content().strip() == 'Campus', murdoch_parsing_error
    assert header[3].text_content().strip() == 'Location', murdoch_parsing_error

    campuses = {
        "Perth (South Street)": exposure_tools.reverse_geocode(-32.0679659, 115.8330479),
        "Mandurah": exposure_tools.reverse_geocode(-32.5157925, 115.7537496),
        "Rockingham": exposure_tools.reverse_geocode(-32.2779483, 115.749966)
    }
    exposures = []

    for row in rows:
        str_date = html_clean_string(row[0].text_content().strip())
        str_time = html_clean_string(row[1].text_content().strip())
        campus = html_clean_string(row[2].text_content().strip())
        location = html_clean_string(row[3].text_content().strip())

        date = dt.datetime.strptime(str_date, "%d %B").replace(year=NOW.year)
        str_time_start, str_time_end = str_time.replace(" noon", ".00pm").replace("noon", ".00pm").replace(":", ".").split(" – ")
        if str_time_start[-1] != "m":
            str_time_start += str_time_end[-2:]
        start_time = dt.datetime.strptime(str_time_start, "%I.%M%p")
        end_time = dt.datetime.strptime(str_time_end, "%I.%M%p")

        address = campuses[campus]
        exposure = exposure_tools.Exposure(dt.datetime.combine(date, start_time.time()), address, location, dt.datetime.combine(date, end_time.time()))
        exposures.append(exposure)

    return exposures