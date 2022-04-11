#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
from typing import List
from unittest import result
from datetime import datetime
from cdp_backend.pipeline.ingestion_models import EventIngestionModel
import requests
import dc
import re
###############################################################################
ingestionModel = dc.get_events_on_date(datetime(2022, 2, 1))
# dc.get_static_person_info()
# dc.dump_static_info(dc.STATIC_FILE_DEFAULT_PATH)
# print(ingestionModel)
# mail = 'mailto:jjessie@dccouncil'
# re.compile(r'mailto:{.*}@dccouncil.us' , mail)
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