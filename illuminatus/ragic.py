import os, sys, re

import http.client
import urllib
import configparser
import json
from pprint import pprint

import logging
L = logging.getLogger(__name__)

# Basic client for the Ragic API - see
# https://github.com/ragic/public/blob/master/HTTP%20API%20Sample/Python-Sample/read.py
# This client has no extra dependencies - just Py3 standard lib
USE_RAGIC = (os.environ.get("USE_RAGIC") == "yes")

class RequestError(RuntimeError):
    pass

def get_project_names(*pnum_list, rc=None):
    """Connect to the Ragic and translate one or more project names.
    """
    if not rc:
        rc = RagicClient.connect_with_creds()

    # re-format
    pnum_list = ["{:05d}".format(int(pnum)) for pnum in pnum_list]

    # Query on "Sequencing Project" by "Project Number". No need to specify the project
    # type, I think, but it should be "Illumina".
    query_form  = "sequencing/1"   # Sequencing Project
    query_field = "1000001"        # Project Number

    query_list = [ f"{query_field},eq,{pnum}" for pnum in pnum_list]
    projects = rc.list_entries(query_form, query_list)
    projects = sorted(projects.values(), key=lambda p: int(p['_ragicId']))

    # I need to return a list of project names in the same order as the pnum_list
    res = [None] * len(pnum_list)
    for idx, pnum in enumerate(pnum_list):
        matching_projects = [ p for p in projects if p['Project Number'] == pnum ]

        if not matching_projects:
            L.warning(f"No Ragic entry found for {pnum!r}")
        else:
            res[idx] = matching_projects[-1]['Project Name']

    return res

def get_project_name(pnum, rtm):
    """Given an existing RT connection, translate a single project name
    """
    pnum = "{:05d}".format(int(pnum))

    ticket_id, ticket_dict = rtm.search_project_ticket(pnum)
    if not ticket_id:
        L.warning(f"No ticket found for '{pnum}'")
        return None

    ticket_subject = ticket_dict['Subject']

    L.debug(f"Ticket #{ticket_id} for '{pnum}' has subject: {ticket_dict.get('Subject')}")
    mo = re.search(rf" ({pnum}_\w+)", ticket_subject)

    return mo.group(1)


class RagicClient:

    def __init__(self, server_url):

        # Server may or may not have https:// part
        if '://' in server_url:
            self.server_url = server_url
        else:
            self.server_url = f"https://{server_url}"

        self.http_timeout = 30

    def connect(self, account_name, api_key):
        """Not really a connection as the API is stateless.
        """
        self.account_name = account_name
        self.api_key = api_key

        # To allow chaining
        return self

    @classmethod
    def connect_with_creds(cls, ini_section="ragic"):
        """Use ~/.ragic_api to connect
        """
        # Master switch for this, because I don't want any tests to be connecting to Ragic.
        if not USE_RAGIC:
            raise RuntimeError("Ragic is turned off. Set USE_RAGIC=yes to enable it.")

        config = configparser.SafeConfigParser()
        conf_file = config.read(os.environ.get('RAGICAPIFILE',
                                [os.path.expanduser('~/.ragic_api'), 'ragic_api.conf']))

        assert conf_file, "No config file found for Ragic API credentials"
        res = config[ini_section]

        return cls(res['server']).connect( account_name = res['account'],
                                           api_key = res['key'] )

    def list_entries(self, sheet, query=None):

        listing_page = self._get_page_url(sheet)

        params = {}
        if query:
            params['where'] = query

        return self._get_json(listing_page, params)

    def get_page(self, sheet, record_id):

        entry_page = self._get_page_url(sheet, record_id)

        return self._get_json(entry_page)

    def _get_json(self, url, params=None):
        """Get a URL with all the right credentials and headers
        """
        mo = re.match(r'https://([^/]+)(/.*)?', url)
        host = mo.group(1)
        path = mo.group(2)

        params = urllib.parse.urlencode(params, doseq=True)

        try:
            conn = http.client.HTTPSConnection(host, timeout=self.http_timeout)

            conn.request("GET", f"{path}?{params}", headers = self._get_headers())

            resp = conn.getresponse()

            if resp.status != 200:
                raise RequestError(f"{resp.status} {resp.reason}")

            return json.load(resp)
        finally:
            conn.close()

    def _get_page_url(self, sheet, record_id=None):

        page = f"{self.server_url}/{self.account_name}/{sheet}"
        if record_id is not None:
            page += f"/{record_id}"

        return page

    def _get_params(self, **overrides):

        params = dict( api = "", v = "3" )
        params.update(overrides)
        return params

    def _get_headers(self, **overrides):

        headers = dict( Authorization = f"Basic {self.api_key}" )
        headers.update(overrides)
        return headers

