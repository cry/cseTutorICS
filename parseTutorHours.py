#!/usr/bin/env python

import urllib2, urllib, sys, random
import time, pytz
import getpass, base64, json

from hashlib import md5
from bs4 import BeautifulSoup as bs
from datetime import datetime

''' Constants '''

# Unsure if we need to account for daylight savigns

TIMEZONE = pytz.timezone("Australia/Sydney")

SECONDS_HOUR = 3600
SECONDS_DAY = 86400
SECONDS_WEEK = 604800
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Academic dates are assumed to begin at 00:00:00 and end at 23:59:59

ACADEMIC_DATES = {
    "17s2": {
        "start": 1500818400,
        "end": 1511182799
    },
    "17x1": {
        "start": 1511787599,
        "end": 1518440399
    },
    "18s1": {
        "start": 1519563600,
        "end": 1529935199
    },
    "18s2": {
        "start": 1532268000,
        "end": 1542718799
    }
}

''' Templates '''

ICS_HEADER = open("ics_header.txt", "r").read()
EVENT_TEMPLATE = open("event_template.txt", "r").read()

''' Determine the current year && session '''

current_year = current_session = None

for session in ACADEMIC_DATES:
    if int(time.time()) >= ACADEMIC_DATES[session]["start"] and int(time.time()) <= ACADEMIC_DATES[session]["end"]:
        current_year = session[0:2]
        current_session = session[2:]
        current_full_session = session
        break

if current_year is None:
    raise Exception("Not in a valid session")


ALLOCATION_URL = "https://cgi.cse.unsw.edu.au/~teachadmin/casual_academics/%s%s/apply/allocation.cgi" % (current_year, current_session)
#ALLOCATION_URL = "https://carey.li/p/tut_test.php" # Test URL
CLASSUTIL_API_URL = "https://classutil.carey.li/api?f=comp&s=%s" % (current_session)

try:
    classdata = json.loads(urllib2.urlopen(CLASSUTIL_API_URL).read())
except:
    raise Exception("Cannot retrieve classdata from classutil api.")

zid = raw_input("zID: ")
zpass = getpass.getpass("zPass: ")

data = urllib.urlencode({"zid": zid, "zpass": zpass})
res = urllib2.urlopen(ALLOCATION_URL, data).read()
bs_res = bs(res, "html.parser")

if bs_res.pre is None:
    raise Exception("Invalid zid or zpass")

chain = bs_res.pre.get_text().split("\n")[1:-1]

final_ics = ICS_HEADER.replace("__ZID__", zid) \
                      .replace("__UUID__", "%s@tutorgen.carey.li" % (md5(zid).hexdigest()))

for tut in chain:
    st = tut.split()
    course = st[0]

    if st[1] == "weeks": code = ""
    else: code = st[1]

    # Some labs are called TLB, don't know why

    full_data = classdata[course]["LAB" if "LAB" in classdata[course] else "TLB"]
    loc_string = None

    if len(full_data) == 1 or code == "": loc_string = full_data[0]["location"]
    else:
        for lab in full_data:
            if lab["code"] == code:
                loc_string = lab["location"]
                break

        if loc_string is None:
            raise Exception("Can't find your lab: %s %s" % (course, code))

    for token in loc_string.split(";"):
        token = token.split()
        print token

        weeks = token[2][2:-1].split(",")

        for index, interval in enumerate(weeks):
            start, end = map(int, interval.split("-"))
            start_epoch = ACADEMIC_DATES[current_full_session]["start"]

            hours = map(int, token[1].split("-"))

            # Tuts don't specify a end hour, assuming they only take 1 hour for now
            if len(hours) == 1: hours.append(hours[0] + 1)

            if start != 1:
                start_epoch += (start - 1) * SECONDS_WEEK

            # Create the day offset & generate epoch start and end times
            start_epoch += DAYS.index(token[0]) * SECONDS_DAY

            class_start = start_epoch + hours[0] * SECONDS_HOUR
            class_end = start_epoch + hours[1] * SECONDS_HOUR

            end_epoch = ACADEMIC_DATES[current_full_session]["start"] + (end - 1) * SECONDS_WEEK + DAYS.index(token[0]) * SECONDS_DAY + hours[1] * SECONDS_HOUR

            # Special location parsing because inconsistent formatting

            if len(token) != 5: location = token[3].replace(")", "")
            else: location = "%s %s" % (token[3], token[4].replace(")", ""))

            # TODO: Clean up this mess
            # The replace and string substrs change the time into ics format time

            final_ics += EVENT_TEMPLATE.replace("__UUID__", "%s@tutorgen.carey.li" % (md5("%d %s" % (random.randint(1, 1e10), code)).hexdigest())) \
                                       .replace("__DTSTAMP__", datetime.fromtimestamp(time.time(), TIMEZONE).isoformat().replace("-", "").replace(":", "")[:-12]) \
                                       .replace("__SUMMARY__", "%s Tutorial" % course) \
                                       .replace("__DESC__", "%s %s" % (course, code)) \
                                       .replace("__TSTART__", datetime.fromtimestamp(class_start, TIMEZONE).isoformat().replace("-", "").replace(":", "")[:-5]) \
                                       .replace("__TEND__", datetime.fromtimestamp(class_end, TIMEZONE).isoformat().replace("-", "").replace(":", "")[:-5]) \
                                       .replace("__REND__", datetime.fromtimestamp(end_epoch, TIMEZONE).isoformat().replace("-", "").replace(":", "")[:-5]) \
                                       .replace("__DAY__", token[0][0:2].upper()) \
                                       .replace("__LOCATION__", location) \



final_ics += "END:VCALENDAR"
open("%s.ics" % zid, "w").write(final_ics)
print "Wrote to %s.ics" % zid
