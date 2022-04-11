#!/usr/bin/env python
# -*- coding: utf-8 -*-
from distutils.log import debug
import logging
import os
import json
from datetime import datetime, timedelta
import io
from httplib2 import Response
from pathlib import Path
from pydantic import Json
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
import time
from cdp_backend.database.constants import (
    EventMinutesItemDecision,
    MatterStatusDecision,
    VoteDecision,
)
from datetime import datetime
from typing import Dict, List, NamedTuple, Optional
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from bs4 import BeautifulSoup
from logging import getLogger
from time import time, sleep
import re
from cdp_backend.pipeline.ingestion_models import (
    Body,
    EventIngestionModel,
    Session,
    EventMinutesItem,
    MinutesItem,
    Vote,
    Matter,
    Person,
    Seat
)
# load_dotenv()
log = logging.getLogger(__name__)
TOKEN = os.environ.get('TOKEN')
STATIC_FILE_DEFAULT_PATH = Path(__file__).parent / "dc-static.json"
STATIC_FILE_KEY_PERSONS = "persons"
known_persons: Dict[str, Person] = {}

# load long-term static data at file load-time
if Path(STATIC_FILE_DEFAULT_PATH).exists():
    with open(STATIC_FILE_DEFAULT_PATH, "rb") as json_file:
        static_data = json.load(json_file)

    for name, person in static_data[STATIC_FILE_KEY_PERSONS].items():
        known_persons[name] = Person.from_dict(person)


if len(known_persons) > 0:
    log.debug(f"loaded static data for {', '.join(known_persons.keys())}")
###############################################################################

log = getLogger(__name__)
STATIC_FILE_KEY_PERSONS = "persons"
MATTER_ADOPTED_PATTERNS = [
    "accepted",
    "passed",
    "adopted",
    "confirmed",
]
COUNCIL_NAME = {
  'White, Robert C. Jr.':'Robert C. White, Jr',
  'Gray, Vincent C. ':'Vincent C. Gray',
  'Nadeau, Brianne K.':'Brianne K. Nadeau',
  'Cheh, Mary M.':'Mary Cheh',
  'Allen, Charles':'Charles Allen',
  'Bonds, Anita':'Anita Bonds',
  'McDuffie, Kenyan R. ':'Kenyan R. McDuffie',
  'Pinto, Brooke':'Brooke Pinto',
  'Silverman, Elissa':'Elissa Silverman',
  'Lewis George, Janeese':'Janeese Lewis George',
  'White, Trayon Sr.':'Trayon White, Sr',
  'Henderson, Christina':'Christina Henderson',
  'Mendelson, Phil':'Phil Mendelson',
}
_vote_status = {
    "approved": "pass",
    "disapproved": "fail",
    "failed": "fail",
    "declined": "fail",
    "passed": "pass",
}
MATTER_IN_PROG_PATTERNS = [
    "passed to",
    "placed on",
    "continued",
    "referred",
]

MINUTE_ITEM_PASSED_PATTERNS = [
    # NOTE: these words while have positive conotation,
    # does not mean the legistation was passed.
    # it indicates the item (or a report, etc.) was accepted to be discussed and voted.
    # "accepted",
    # "confirmed",
    # "adopted",
    "passed$",
]
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
_API_BASE_URL = "https://lims.dccouncil.us/api/v2/PublicData/LegislationDetails/"

_HEADER = {
        "Authorization": '1607b76f-60c7-40d6-a0ce-d8c81b65a7a1',
        "Accept": "application/json",
    }
class SlidingWindow:

    def __init__(self, capacity, time_unit):
        self.capacity = capacity
        self.time_unit = time_unit
        self.cur_time = time()
        self.pre_count = capacity
        self.cur_count = 0

    def handle(self, packet ,action):

        if (time() - self.cur_time) > self.time_unit:
            self.cur_time = time()
            self.pre_count = self.cur_count
            self.cur_count = 0

        ec = (self.pre_count * (self.time_unit - (time() - self.cur_time)) / self.time_unit) + self.cur_count

        if (ec > self.capacity):
            return self.drop(packet)

        self.cur_count += 1
        return self.forward(action)


    def forward(self , action) -> json:
        action = re.sub(r'Bill' , r'B' , action) # adapting to Bill / B legislation number for parsing request
        if re.findall(r'((PR|B|CER|CA)\d{1,2}-\d{3})\b' , action):
           action = re.sub(r'((PR|B|CER|CA)\d{1,2}-)\b',r'\g<1>0' , action)
        r = requests.get(  
            url=_API_BASE_URL + action,
            headers=_HEADER,
        )
        try:
            return r.json()
        except: 
            return []    

    def drop(self):
        return []
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
    if agenda_uri:
        minutes_item:List[EventMinutesItem] = []
        rate_limit = 4
        throttle = SlidingWindow(rate_limit, 1)
        packet = 0
        r = requests.get(agenda_uri)
        f = io.BytesIO(r.content)
        doc = fitz.open("pdf",f)  # open document
        for page in doc:  # iterate the document pages (number of pages in pdf)
            text = page.get_text().encode("utf8") # conversion to byte like object to avoid string white space conflict 
            result =  re.findall(rb'((PR|Bill|CER|CA) \d{1,2}-\d{1,4})\b' , text)
            for action in result:
                sleep(0.2)
                minute_section = throttle.handle(packet ,re.sub(r'((PR|Bill|CER|CA) \d{1,2}-)\b',r'\g<1>0' , action[0].decode("utf8")).replace(" ", ""))
                # NOTE when searching using legislationNumber it is advised to follow the 4-digit pattern. 
                # e.g⇒ content parsed from text conversion (Bill 24-462) ⇒ pattern( type_of_action+period_id+’-’+4digit  ) ⇒ B24-0462 
                packet += 1 
                
                minutes_item.append( EventMinutesItem(
                    minutes_item = MinutesItem(name=action[0].decode("utf8"), description=minute_section['additionalInformation']),
                    matter = get_matter(minute_section),
                    decision=EventMinutesItemDecision.PASSED,
                    votes=None
                    # index=0,
                ))
        return minutes_item        
    else :
        return None
def get_matter(minute_section: json) -> Optional[Matter]:
    # Sponsors 
    sponsor_list: List[Person] = []
    for i in minute_section["introducers"]:
        sponsor_list.append(
           get_person(i["memberName"])     
        )
    print(minute_section['actions'])    
    return Matter(
        matter_type=None, 
        name=minute_section['legislationNumber'],
        sponsors=sponsor_list,
        title=minute_section['title'],
        result_status=MatterStatusDecision.IN_PROGRESS
    )
def get_votes(action: str) -> Optional[List[Vote]]:
    vote_list:List[Vote] = []
    try :
        Vote(

        )
        # r.raise_for_status()
        pass
    except (URLError, HTTPError) as e:
        # code  = e.response.status_code
        # log.warning(
        #     e.response.text
        # )
        return None    
def get_person( name: str) -> Person:
    
    if name not in COUNCIL_NAME:
        raise KeyError(f"{name} is unknown. Please update dc-static.json")
    return known_persons[COUNCIL_NAME[name]] 
    


def get_static_person_info() -> Dict[str, Person]:
    """
    Scrape current council members information from dc.gov

    Returns
    -------
    persons: Dict[str, Person]
        keyed by name

    Notes
    -----
    Parse https://dccouncil.us/councilmembers/
    that contains list of current council members name, position, contact info, political affiliation
    """
    # this page lists current council members
    with urlopen(
        "https://dccouncil.us/councilmembers/"
    ) as resp:
        soup = BeautifulSoup(resp.read(), "html.parser")
     
    # keyed by name
    persons: Dict[str, Person] = {}
    sp = soup.select("figure + a" , href=re.compile(r'https://dccouncil.us/council/'))
    for link in sp :
        with urlopen(
            link['href']
        ) as resp:
            soup = BeautifulSoup(resp.read(), "html.parser")
            picture_uri = soup.select('figure a img')[0]['src']
            name = soup.select('h1')[0].text
            email = soup.find("a",href=re.compile(r'mailto:.*?@dccouncil'))['href'].replace('mailto:','')
            phone = soup.find("a",href=re.compile(r'tel:.*?'))['href'].replace('tel:','')
            web = soup.find("a",href=re.compile(r'http:.*?.com'))
            web = web['href'] if web else None
        persons[name] = Person(
            name=name,
            picture_uri=picture_uri,
            email=email,
            website=web,
            phone=phone,
            seat=None,
        )

    return persons


def dump_static_info(file_path: Path) -> None:
    """
    Call this to save current council members information as Persons
    in json format to file_path.
    Intended to be called once every N years when the council changes.

    Parameters
    ----------
    file_path: Path
        output json file pathSTATIC_FILE_KEY_PERSONS = "persons"
    """
    pass
    static_info_json = {STATIC_FILE_KEY_PERSONS: {}}
    for [name, person] in get_static_person_info().items():
        # to allow for easy future addition of info other than Persons
        # save under top-level key "persons" in the file
        static_info_json[STATIC_FILE_KEY_PERSONS][name] = person.to_dict()

    with open(file_path, "wt") as dump:
        dump.write(json.dumps(static_info_json, indent=4))

        
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
                break
        else:
            agenda_uri = None
        body = get_body(event_page_soup)
        events.append(
            EventIngestionModel(
                body=body,
                agenda_uri=agenda_uri,
                sessions=get_sessions(body.name, event_time),
                event_minutes_items= get_event_minutes(agenda_uri)
            )
        )

    return events

