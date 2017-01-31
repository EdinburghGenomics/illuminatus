'''
Created on 30 Apr 2013
Updated Jan 2017

@author: tcezard, tbooth2, mberinsk
'''
import os, re
import configparser

import rt
from rt import AuthorizationError, InvalidUse


""" All this gubbins now lives in the .ini file.
RT_TEST_SERVER = "http://rt-test.genepool.private"
RT_SERVER = "http://rt.genepool.private"

#Queues
DEFAULT_QUEUE = "bfx-general"
PROJECT_QUEUE = "bfx-projects"
QC_QUEUE = "bfx-qc"
RUN_QUEUE = "bfx-run"
DELIVERY_QUEUE = "bfx-delivery"

#Requestors
RUN_REQUESTOR = "pipeline"
QC_REQUESTOR = "pipeline"
PROJECT_REQUESTOR = "pipeline"
DELIVERY_REQUESTOR = "pipeline"

#Default ticket CCs
RUN_CC = ""
QC_CC = "genepool-manager@ed.ac.uk, hgunter, rtalbot, genepool-solexa@ed.ac.uk, genepool-bioinformatics@ed.ac.uk"
DELIVERY_CC = ""

# Default owners
PROJECT_OWNER = "pipeline"
"""


class RT_manager():
    def __init__(self, config_name):
        """Communication with RT is managed via the RT module.
           This wrapper picks up connection params from an .ini file,
           which must exist before you can even instatiate the object.

           To actually connect, either call connect() explicitly or say:
             with RT_manager('test-rt') as rt_conn:
                ...
           to connect implicitly.
        """
        self._config_name = config_name
        self._config = self._get_config_from_ini(config_name)

        self.tracker = None

    def connect(self):

        self.server_path = self._config['server']
        self.username, self.password = self._config['user'], self._config['pass']
        self.default_queue = self._config['default_queue']

        self.tracker = rt.Rt( '/'.join([self.server_path, 'REST', '1.0']),
                              self.username,
                              self.password,
                              default_queue=self.default_queue)

        if not self.tracker.login():
            raise AuthorizationError('login() failed on {_config_name} ({tracker.url})'.format(self))

        return self

    #Allow us to use this in a 'with' clause.
    def __enter__(self):
        return self.connect()
    def __exit__(self, *exc):
        #Can you logout of RT? Do you want to?
        pass

    def _get_config_from_ini(self, section_name):

        #Either read the confif pointed to by RT_SETTINGS or else the default.
        #Don't attempt to read both, even though ConfigParser supports it.
        file_name = os.environ.get('RT_SETTINGS')
        file_name = file_name or os.path.join(os.path.expanduser('~'), '.rt_settings')

        cp = configparser.ConfigParser()
        if not cp.read(file_name):
            raise AuthorizationError('unable to read configuration file {file_name}'.format(**locals()))

        #A little validation
        if section_name not in cp:
            raise AuthorizationError('file {file_name} contains no configuration section {section_name}'.format(**locals()))

        conf_section = cp[section_name]

        #A little more validation
        if not all([conf_section.get(x) for x in 'server user pass default_queue'.split()]):
            raise AuthorizationError('file {file_name} did not contain all settings needed for RT authentication'.format(**locals()))

        return conf_section


    """
    Added for illuminatus
    """
    def find_or_create_run_ticket(self, run_id, subject, text=None):
        """Create a ticket for run only if it does not exist already.
           If text is specified it will be used as the request blurb,
           or for existing tickets it will be added as a reply.
        """
        c = self._config
        ticket_id = self.search_run_ticket(run_id)
        if not ticket_id or int(ticket_id) < 1:
            ticket_id = self.tracker.create_ticket(
                Subject   = subject,
                Queue     = c['run_queue'],
                Requestor = c['requestor'],
                Cc        = c.get('run_cc'),
                Text      = text or "" )
        elif text is not None:
            self.reply_to_ticket(ticket_id, text)

        return ticket_id

    def search_run_ticket(self, run_id):
        """Search for a ticket referencing this run, and return the ticket number,
           as an integer, or return None if there is no such ticket.
        """
        c = self._config
        tickets = self.tracker.search( Queue = c['run_queue'],
                                       Subject__like = '%{}%'.format(run_id))

        if len(tickets) == 1:
            return int(tickets[0].get('id').strip('ticket/'))
        elif len(tickets) > 1:
            raise InvalidUse("More than one open ticket for run {}".format(run_id))

        #Failing that...
        return None

    def reply_to_ticket(self, ticket_id, message, **kwargs):
        return self.tracker.reply(ticket_id, text=message, **kwargs)

    def comment_on_ticket(self, ticket_id, message, **kwargs):
        return self.tracker.comment(ticket_id, text=message, **kwargs)

    def change_ticket_status(self, ticket_id, status):
        kwargs = dict( Status = status )
        try:
            return self.tracker.edit_ticket(ticket_id, **kwargs)
        except IndexError:
            pass # if the status is the same getting this exception

    def change_ticket_subject(self, ticket_id, subject):
        """You can reply to a ticket with a one-off subject, or you can edit the
           subject of the whole ticket. This does the latter. Think carefully about
           which you need.
           FIXME - fix this comment.
           FIXME2 - why the extra space??
        """
        kwargs = dict( Subject = "{} ".format(subject) )
        try:
            return self.tracker.edit_ticket(ticket_id, **kwargs)
        except IndexError:
            pass # if the subject is the same getting this exception

