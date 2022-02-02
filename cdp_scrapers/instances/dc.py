#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import json
from datetime import datetime, timedelta
from typing import List, Optional
from dotenv import load_dotenv
from cdp_backend.pipeline.ingestion_models import EventIngestionModel
from requests import request
from cdp_scrapers.scraper_utils import IngestionModelScraper
from cdp_scrapers.types import ContentURIs
from urllib import request 

load_dotenv()
TOKEN = os.environ.get('TOKEN')
###############################################################################
class DCScraper():
    def __init__(self) :
        super().__init__(
            client="DC",
            timezone="America/New_York",
        )
    def parse_content_uris(
        self, video_page_url: str, event_short_date: str
    ) -> List[ContentURIs]:
        """
        Return URLs for videos and captions parsed from seattlechannel.org web page

        Parameters
        ----------
        video_page_url: str
            URL to a web page for a particular meeting video

        event_short_date: str
            datetime representing the meeting's date, used for verification m/d/yy

        Returns
        -------
        content_uris: List[ContentURIs]
            List of ContentURIs objects for each session found.

        See Also
        --------
        get_content_uris()
        """

    def get_event(self, event_time: datetime) -> Optional[EventIngestionModel]:
        headers = {
            'Authorization': TOKEN ,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        data = {
            "keyword": "Committee on Transportation & the Environment",
            "categoryId": 0,
            "subCategoryId": 0,
            "councilPeriodId": 0,
            "rowLimit": 1,
            "offSet": 0,
            "statusId": 0
        }   
        url = 'https://lims.dccouncil.us/api/v2/PublicData/SearchLegislation'

        encoded_data = json.dumps(data).encode()

        req = request.Request(url=url, data=encoded_data , headers=headers)
        response = request.urlopen(req)

        text = response.read()

        print(len(json.loads(text.decode('utf-8'))))
    def get_video_uri():
        pass    
    def get_events(
        self,
        begin: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[EventIngestionModel]:
        """
        Get all events for the provided timespan.

        Parameters
        ----------
        from_dt: datetime
            Datetime to start event gather from.
        to_dt: datetime
            Datetime to end event gather at.

        Returns
        -------
        events: List[EventIngestionModel]
            All events gathered that occured in the provided time range.

        Notes
        -----
        As the implimenter of the get_events function, you can choose to ignore the from_dt
        and to_dt parameters. However, they are useful for manually kicking off pipelines
        from GitHub Actions UI.
        """
        if begin is None:
            begin = datetime.utcnow() - timedelta(days=2)
        if end is None:
            end = datetime.utcnow()
        
        # Your implementation here
        return []
