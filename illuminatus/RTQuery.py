#!/usr/bin/env python3
import os, sys, re
from contextlib import suppress
import configparser
from rt import Rt, AuthorizationError

import logging
L = logging.getLogger(__name__)

rt_config_name = os.environ.get('RT_SYSTEM', 'production-rt')

def get_project_names(*pnum_list):
    """Connect to the database and translate one or more project names
    """
    res = []
    with RTManager() as rtm:
        for pnum in pnum_list:
            res.append(get_project_name(pnum, rtm))

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

class RTManager():
    def __init__(self, config_name=None , queue_setting=None):
        """Communication with RT is managed via the RT module.
           This wrapper picks up connection params from an .ini file,
           which must exist before you can even instatiate the object.

           To actually connect, either call connect() explicitly or say:
             with RTManager('test-rt') as rt_conn:
                ...
           to connect implicitly.
        """
        self._config_name = config_name or os.environ.get('RT_SYSTEM', "production-rt")
        self._queue_setting = queue_setting or "eg-projects" # eg. pbrun, run
        if self._config_name.lower() == "none":
            # Special case for short-circuiting RT entirely, whatever the .ini
            # file says, by setting RT_SYSTEM=none
            self._config = None
        else:
            self._config = self.get_config_from_ini(self._config_name)

        self.tracker = None

    def connect(self, timeout=60):

        if not self._config:
            L.warning("Making dummy connection - all operations will be no-ops.")
            return self

        self.server_path = self._config['server']
        self.username, self.password = self._config['user'], self._config['pass']
        self._queue = self._config.get(f"{self._queue_setting}_queue", self._queue_setting)

        self.tracker = Rt( '/'.join([self.server_path, 'REST', '1.0']),
                           self.username,
                           self.password,
                           default_queue = self._queue )

        if not self.tracker.login():
            raise AuthorizationError(f'login() failed on {self._config_name} ({self.tracker.url})')

        # Here comes the big monkey-patch-o-doom!
        # It will force a 60-second timeout on the Rt session, assuming the internal implementation
        # of session is not changed in the requests library.
        from types import MethodType
        foo = self.tracker.session
        foo._merge_environment_settings = foo.merge_environment_settings
        foo.merge_environment_settings = MethodType(
                lambda s, *a: dict([*s._merge_environment_settings(*a).items(), ('timeout', s.timeout)]),
                foo )
        foo.timeout = timeout
        # End of monkey business

        return self

    # Allow us to use this in a 'with' clause.
    def __enter__(self):
        return self.connect()
    def __exit__(self, *exc):
        # Can you logout of RT? Do you want to?
        pass


    def get_config_from_ini(self, section_name):
        """Either read the config pointed to by RT_SETTINGS or else the default.
           Don't attempt to read both, even though ConfigParser supports it.
        """
        file_name = os.environ.get('RT_SETTINGS')
        file_name = file_name or os.path.join(os.path.expanduser('~'), '.rt_settings')

        cp = configparser.ConfigParser()
        if not cp.read(file_name):
            raise AuthorizationError(f'unable to read configuration file {file_name}')

        # A little validation
        if section_name not in cp:
            raise AuthorizationError(f'file {file_name} contains no configuration section {section_name}')

        conf_section = cp[section_name]

        # A little more validation
        for x in ['server', 'user', 'pass']:
            if not conf_section.get(x):
                raise AuthorizationError(f"file {file_name} did not contain setting {x} needed for RT authentication")

        return conf_section

    # The actual method
    def search_project_ticket(self, project_number):
        """Search for a ticket referencing this project, and return the ticket number,
           as an integer, along with the ticket metadata as a dict,
           or return (None, None) if there is no such ticket.
        """
        c = self._config

        tickets = list(self.tracker.search( Queue = self._queue,
                                            Subject__like = f'% {project_number}_%',
                                          ))

        if not tickets:
            return (None, None)

        # Order the tickets by tid and get the highest one
        def get_id(t): return int(t['id'].strip('ticket/'))
        tickets.sort(key=get_id, reverse=True)
        tid = get_id(tickets[0])

        if len(tickets) > 1:
            L.warning(f"Warning: We have {len(tickets)} tickets matching {project_number}."
                      f" Using the latest, {tid}")

        #Failing that...
        return (tid, tickets[0]) if tid > 0 else (None, None)
