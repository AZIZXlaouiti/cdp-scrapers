#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import json
from datetime import datetime, timedelta
import io
import requests
import fitz
import re
from typing import List, Optional
# from dotenv import load_dotenv
from cdp_backend.pipeline.ingestion_models import EventIngestionModel
from requests import request
from cdp_scrapers.scraper_utils import IngestionModelScraper
from cdp_scrapers.types import ContentURIs
from urllib import request 

# load_dotenv()
TOKEN = os.environ.get('TOKEN')
###############################################################################
from datetime import datetime
from typing import Dict, List, NamedTuple, Optional
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from bs4 import BeautifulSoup
from logging import getLogger
import re
from cdp_backend.pipeline.ingestion_models import (
    Body,
    EventIngestionModel,
    Session,
    EventMinutesItem,
    MinutesItem,
)


log = getLogger(__name__)


# http://dc.granicus.com/viewpublisher.php?view_id=2
COMMITTEE_VIDEO_ARCHIVES: Dict[str, str] = {
    # each page lists all meeting videos and captions for the committee
    "City Council": "http://dc.granicus.com/ViewPublisher.php?view_id=3",
    "Committee of the Whole": "http://dc.granicus.com/ViewPublisher.php?view_id=4",
    "Committee on Transportation and the Environment":
        "http://dc.granicus.com/ViewPublisher.php?view_id=29",
    "Committee on Human Services":
        "http://dc.granicus.com/ViewPublisher.php?view_id=11",
    "Committee on Judiciary and Public Safety":
        "http://dc.granicus.com/ViewPublisher.php?view_id=44",
    "Committee on Labor and Workforce Development":
        "http://dc.granicus.com/ViewPublisher.php?view_id=45",
    "Committee on Education": "http://dc.granicus.com/ViewPublisher.php?view_id=30",
    "Committee on Housing and Executive Administration":
        "http://dc.granicus.com/ViewPublisher.php?view_id=52",
    "Committee on Health": "http://dc.granicus.com/ViewPublisher.php?view_id=9",
    "Committee on Business and Economic Development":
        "http://dc.granicus.com/ViewPublisher.php?view_id=41",
    "Committee on Recreation, Libraries, and Youth Affairs":
        "http://dc.granicus.com/ViewPublisher.php?view_id=54",
    "Committee on Facilities and Procurement":
        "http://dc.granicus.com/ViewPublisher.php?view_id=49",
    "Committee on Government Operations and Facilities":
        "http://dc.granicus.com/ViewPublisher.php?view_id=53",
    "Subcommittee on Redistricting":
        "http://dc.granicus.com/ViewPublisher.php?view_id=22",
    "Special Committee for Covid19 Pandemic Recovery":
        "http://dc.granicus.com/ViewPublisher.php?view_id=51",
}


def get_sessions(body_name: str, event_time: datetime) -> Optional[List[Session]]:
    for video_body, video_archive in COMMITTEE_VIDEO_ARCHIVES.items():
        if body_name.lower() in video_body.lower():
            try:
                # load the video listing
                with urlopen(video_archive) as resp:
                    soup = BeautifulSoup(resp.read(), "html.parser")
            except (URLError, HTTPError) as inst:
                log.warning(f"{video_archive}: {str(inst)}")
                return None

            sessions: List[Session] = []
            session_index = 0
            # look for Date column with the event's date mm/dd/yy
            # <td headers="Date..."><span>...</span>02/15/22</td>
            try:
                for row in [
                    i.parent
                    for i in soup.find("table", id="archive").find_all(
                        "td", headers=re.compile("Date")
                    )
                    if i.text.endswith(event_time.strftime("%m/%d/%y"))
                ]:
                    # we now want the mp4 link and the captions link
                    # each in its <td> like the date above
                    caption_uri = row.find(
                        'td',
                        headers=re.compile('Captions'),
                    ).find('a')['href']
                    sessions.append(
                        Session(
                            # NOTE: this is a web page
                            # TODO: dump content to text?
                            caption_uri=f"https:{caption_uri}",
                            session_datetime=event_time,
                            session_index=session_index,
                            video_uri=row.find(
                                "td", headers=re.compile("MP4Link")
                            ).find("a")["href"],
                        )
                    )
                    session_index += 1
            except AttributeError:
                # find() failed
                log.debug(f"no entry on {video_archive} for {event_time.date()}")
                return None

            return sessions

    log.warning(f"{body_name} is not in COMMITTEE_VIDEO_ARCHIVES")
    return None


def get_body(event_page_soup: BeautifulSoup) -> Optional[Body]:
    try:
        # <header class="article-header"> contains the page header text
        # e.g. meeting &bullet; committee of the ...
        # or just
        # e.g. meeting
        # when it's the city council legislative meeting
        header_text_bytes = (
            event_page_soup.find("header", class_="article-header")
            .find("p")
            .text.encode("utf-8")
        )
    except AttributeError:
        # find() failed
        log.warning(
            "Error finding header line. DC may have changed their event page HTML"
        )
        return None

    # look for words following the bullet character
    body_name_regex = re.search(b"\xe2\x80\xa2(.+)", header_text_bytes)
    if body_name_regex is None:
        # city council
        return Body(name="City Council")

    body_name = body_name_regex.group(1).decode("utf-8").strip()
    if len(body_name) == 0:
        # city council
        return Body(name="City Council")

    return Body(name=body_name)


class EventRelatedMaterial(NamedTuple):
    name: str
    url: str


def get_event_materials(event_page_soup: BeautifulSoup) -> List[EventRelatedMaterial]:
    # event page lists pdf documents in the left side table
    # <section class="aside-section">
    # <ul>
    # <li>
    # <a href="..." class="icon--pdf icon-link">Draft Agenda</a>
    # </li>
    try:
        return [
            EventRelatedMaterial(link.text.strip(), link["href"].strip())
            for link in event_page_soup.find(
                "section", class_="aside-section"
            ).find_all("a", class_="icon--pdf icon-link")
        ]
    except AttributeError:
        # find() failed
        return []

def get_event_minutes(agenda_uri: str) -> Optional[List[EventMinutesItem]]:
    minutes: List[MinutesItem] = []
    r = requests.get(agenda_uri)
    f = io.BytesIO(r.content)
    doc = fitz.open("pdf",f)  # open document
    for page in doc:  # iterate the document pages (number of pages in pdf)
        text = page.get_text().encode("utf8") # conversion to byte like object to avoid string white space conflict 
        result =  re.findall(rb'((PR|Bill|CER|CA) \d{1,2}-\d{1,4})\b' , text)
        for action in result :
            minutes.append(MinutesItem(name=action[0].decode("utf8"), description=None))
    
    return EventMinutesItem(
        decision=None,
        index=0,
        minutes_item=minutes,
    )
def get_events_on_date(event_date: datetime) -> Optional[List[EventIngestionModel]]:
    try:
        # this gets us an events calendar for the month
        with urlopen(
            f"https://dccouncil.us/events/{event_date.strftime('%Y-%m')}"
        ) as resp:
            month_soup = BeautifulSoup(resp.read(), "html.parser")
    except (URLError, HTTPError):
        log.warning(
            f"Error retrieving event calendar for {event_date}.\n"
            "DC may have changed their web site structure."
        )
        return None

    events: List[EventIngestionModel] = []
    # links to events for a given day are under <div> tags with the date in id attr
    for event_div in month_soup.find_all(
        "div",
        id=re.compile(f"tribe-events-event-\\d+-{event_date.strftime('%Y-%m-%d')}"),
    ):
        # link is in the <a class="url"> in this <div>
        event_link_tag = event_div.find("a", class_="url")
        if event_link_tag is None:
            log.debug(f"no event page url for event id {event_date['id']}")
            continue

        log.debug(event_link_tag["href"])
        try:
            with urlopen(event_link_tag["href"].strip()) as resp:
                event_page_soup = BeautifulSoup(resp.read(), "html.parser")
        except (URLError, HTTPError) as inst:
            log.warning(str(inst))
            continue

        # looking for <div><h4>Date</h4><p>date and time string
        # this ends up being like
        # Tuesday,February01,202201:00pmAddtoGoogleCalendarAddtoiCal
        event_time_text = re.sub(
            r"\s+", "", event_page_soup.find("h4", string="Date").parent.find("p").text
        )
        event_time_text = event_time_text.replace("AddtoGoogleCalendarAddtoiCal", "")
        # don't really care about the weekday to parse into datetime
        event_time_text = event_time_text[event_time_text.find(",") + 1 :]
        # February01,202201:00pm
        event_time = datetime.strptime(event_time_text, "%B%d,%Y%I:%M%p")

        # get pdfs linked on the event page; likely will include agenda document
        event_materials = get_event_materials(event_page_soup)
            
        for material in event_materials:
            if "agenda" in material.name.lower():
                agenda_uri = material.url
                event_minutes = get_event_minutes(agenda_uri) 
                break
        else:
            agenda_uri = None
        body = get_body(event_page_soup)
        print(event_minutes)
        events.append(
            EventIngestionModel(
                body=body,
                agenda_uri=agenda_uri,
                sessions=get_sessions(body.name, event_time),
                # event_minutes_items= event_minutes
            )
        )

    return events

