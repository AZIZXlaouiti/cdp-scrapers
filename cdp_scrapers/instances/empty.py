#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
from typing import List
from unittest import result
from datetime import datetime
from cdp_backend.pipeline.ingestion_models import EventIngestionModel
import dc

###############################################################################
import io
import requests
import fitz
import re

# url = 'https://dccouncil.us/wp-content/uploads/2021/12/February-1-2022-Legislative-Meeting-2.pdf'
# r = requests.get(url)
# f = io.BytesIO(r.content)


ingestionModel = dc.get_events_on_date(datetime(2022, 2, 1))
print(ingestionModel)
# doc = fitz.open("pdf",f)  # open document
# for page in doc:  # iterate the document pages number of pages in pdf
#     text = page.get_text().encode("utf8") # conversion to byte like object to avoid string white space confict 
#     result =  re.findall(rb'((PR|Bill|CER|CA) \d{1,2}-\d{1,4})\b' , text)
#     for action in result :
#         print(action[0].decode("utf8"))

def get_events(
    from_dt: datetime,
    to_dt: datetime,
    **kwargs,
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

    # Your implementation here
    return []
