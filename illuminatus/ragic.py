import os, sys, re

import urllib.parse
import urllib.request
import configparser
import json
from pprint import pprint, pformat

import logging
L = logging.getLogger(__name__)

# Basic client for the Ragic API - see
# https://github.com/ragic/public/blob/master/HTTP%20API%20Sample/Python-Sample/read.py
# This client has no extra dependencies - just Py3 standard lib
USE_RAGIC = (os.environ.get("USE_RAGIC") == "yes")

# IDs for fields in my database
# Still not sure if there is a way to introspect the field number to name mapping??
forms = { 'Sequencing Project': { '_form': "sequencing/1",
                                  'Project Number': "1000001",
                                },
          'Illumina Run':       { '_form': "sequencing/2",
                                  'Flowcell ID': "1000011",
                                  'Run ID': "1000037",
                                  'Run QC Report': "1000048",
                                },
          'List of samples':    { '_form': "sequencing/3",
                                  'Project Name': "1000003",
                                }}

class RequestError(RuntimeError):
    pass

class EmptyResultError(RuntimeError):
    pass

def get_project_names(*pnum_list, rc=None):
    """Connect to the Ragic and translate one or more project names.
    """
    if not rc:
        rc = RagicClient.connect_with_creds()
        rc.add_forms(forms)

    # re-format
    pnum_list = ["{:05d}".format(int(pnum)) for pnum in pnum_list]

    # Query on "Sequencing Project" by "Project Number". No need to specify the project
    # type, I think, but it should be "Illumina".
    query_list = [ f"Project Number,eq,{pnum}" for pnum in pnum_list ]
    projects = rc.list_entries("Sequencing Project", query_list)
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

def get_run(fcid, add_samples=False, rc=None):
    """Query a run from Ragic by "Flowcell ID"
    """
    if not rc:
        rc = RagicClient.connect_with_creds()
        rc.add_forms(forms)

    query = f"Flowcell ID,eq,{fcid}"
    runs = rc.list_entries("Illumina Run", query)

    L.debug("Found {len(runs)} record in Ragic.")
    if not runs:
        raise EmptyResultError(f"No record of flowcell ID {fcid}")

    # If there are multiple runs, pick the one with the highest number
    max_record_num = sorted(runs, key=lambda p: int(p))[-1]
    run = runs[max_record_num]

    if add_samples:
        # Now add the lib/barcode info too. We'll fetch all libraries for all projects,
        # which seems simpler than going through the whole list of all libraries in
        # all lanes.
        squery = [ f"Project Name,eq,{proj}" for proj in run['Project'] ]
        squery_result = rc.list_entries("List of samples", squery)

        # This will yield a dict keyed off row IDs, so re-key it by 'LibName'
        run['Samples__dict'] = { v['LibName']: v for v in squery_result.values() }

    return run

def put_run(ragicid, update_items, rc=None):
    """Update values in an Illumina Run
    """
    if not rc:
        rc = RagicClient.connect_with_creds()
        rc.add_forms(forms)

    rc.post_update( "Illumina Run", ragicid, update_items )

def get_rc():
    """Just to avoid the generic Ragic client gaving to know about the specific forms.
    """
    rc = RagicClient.connect_with_creds()
    rc.add_forms(forms)
    return rc

class RagicClient:

    def __init__(self, server_url, forms=None):

        # Server may or may not have https:// part
        if '://' in server_url:
            self.server_url = server_url
        else:
            self.server_url = f"https://{server_url}"

        self.forms = dict()
        if forms:
            self.add_forms(forms)

        self.http_timeout = 30

    def connect(self, account_name, api_key):
        """Not really a connection as the API is stateless.
        """
        self.account_name = account_name
        self.api_key = api_key

        # To allow chaining
        return self

    def add_forms(self, new_forms):
        """Tell the client about some forms.
        """
        # FIXME - if I ever publish this code I should probably deep-copy the dict.
        self.forms.update(new_forms)

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
        """Search for entries by query.
           Query may be a list of '{field},{op},{val}' strings, where
           field may be the ID or else the name of the field in the forms dict.
        """
        sheet_info = None
        if self.forms:
            sheet_info = self.forms[sheet]
            sheet = sheet_info['_form']
        listing_page = self._get_page_url(sheet)

        params = {}
        if query:
            # Replace the named fields
            if sheet_info:
                if isinstance(query, str):
                    query = [query]

                query = [ self._munge_query(q, sheet_info)
                          for q in query ]

            params['where'] = query

        return self._get_json(listing_page, params)

    def get_page(self, sheet, record_id):
        """Fetch as specific record by ID
        """
        if self.forms:
            sheet = self.forms[sheet]['_form']
        entry_page = self._get_page_url(sheet, record_id)

        return self._get_json(entry_page)

    def post_update(self, sheet, record_id, update_items):
        """Save new items into a page.
        """
        if self.forms:
            sheet_info = self.forms[sheet]
            sheet = sheet_info['_form']

            # I also need to translate the dict keys into IDs
            update_items = { sheet_info[k]: v for k, v in update_items.items() }

        entry_page = self._get_page_url(sheet, record_id)

        return self._post_json(entry_page, update_items)

    def _munge_query(self, query, mapping):
        """Fix queries where the first part is a named field by using the mapping.
        """
        query_bits = query.split(",")
        query_bits[0] = mapping[query_bits[0]]
        return ",".join(query_bits)

    def _get_json(self, url, params=None):
        """Get a URL with all the right credentials and headers
        """
        params = self._encode_params(params)

        req = urllib.request.Request( method = "GET",
                                      url = f"{url}?{params}",
                                      headers = self._get_headers() )
        with urllib.request.urlopen( url = req,
                                     timeout = self.http_timeout ) as resp:
            if resp.status != 200:
                raise RequestError(f"{resp.status} {resp.reason}")

            return json.load(resp)

    def _post_json(self, url, json_data, params=None):
        """Post an update with all the right credentials and headers.
        """
        params = self._encode_params(params)

        headers = {'Content-Type': 'application/json'};
        req = urllib.request.Request( method = "POST",
                                      url = f"{url}?{params}",
                                      headers = self._get_headers(**headers) )
        with urllib.request.urlopen( url = req,
                                     data = json.dumps(json_data).encode(),
                                     timeout = self.http_timeout ) as resp:

            if resp.status != 200:
                raise RequestError(f"{resp.status} {resp.reason}")

            # In Ragic, we can have a 200 response but the update may still have been rejected,
            # so check the 'status' AND the 'msg' field.
            json_resp = json.load(resp)
            L.debug(pformat(json_resp))
            if json_resp['status'] != "SUCCESS" or json_resp['msg'] != "&nbsp;":
                raise RequestError(f"{json_resp['status']} {json_resp['msg']}")

    def _get_page_url(self, sheet, record_id=None):

        page = f"{self.server_url}/{self.account_name}/{sheet}"
        if record_id is not None:
            page += f"/{record_id}"

        return page

    def _encode_params(self, overrides):

        params = dict( api = "", v = "3" )
        params.update(overrides or ())
        return urllib.parse.urlencode(params, doseq=True)

    def _get_headers(self, **overrides):

        headers = dict( Authorization = f"Basic {self.api_key}" )
        headers.update(overrides)
        return headers

