'''
Created on 30 Apr 2013
Updated Jan 2017

@author: tcezard, tbooth2, mberinsk
'''
import os, sys, re
from warnings import warn
import configparser

# This is specific to our GSEG server and RT SSL setup, but at least fixing it here
# prevents having to apply the fix to everything that might use
# this library...
if ('REQUESTS_CA_BUNDLE' not in os.environ) and os.path.exists("/etc/pki/tls/certs"):
    os.environ['REQUESTS_CA_BUNDLE'] = "/etc/pki/tls/certs"

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
        if config_name.lower() == 'none':
            #Special case for short-circuiting RT entirely
            self._config = None
        else:
            self._config = self._get_config_from_ini(config_name)

        self.tracker = None

    def connect(self, timeout=60):

        if not self._config:
            warn("Making dummy connection - all operations will be no-ops.")
            return self

        self.server_path = self._config['server']
        self.username, self.password = self._config['user'], self._config['pass']
        self.default_queue = self._config['default_queue']

        self.tracker = rt.Rt( '/'.join([self.server_path, 'REST', '1.0']),
                              self.username,
                              self.password,
                              default_queue=self.default_queue)

        if not self.tracker.login():
            raise AuthorizationError('login() failed on {_config_name} ({tracker.url})'.format(**vars(self)))

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
        """Create a ticket for run if it does not exist already.
           If text is specified it will be used as the request blurb for
           the new ticket but if the ticket already existed it will be
           ignored.
           Returns a pair (ticket_id, created?).
        """
        c = self._config
        ticket_id = self.search_run_ticket(run_id)

        if ticket_id:
            return ticket_id, False

        # Since dummy mode returns 999, we can infer we have a real
        # connection and proceed with real ops.

        # Text munge
        text = re.sub(r'\n', r'\n      ', text.rstrip()) if text \
               else ""

        ticket_id = int(self.tracker.create_ticket(
                Subject   = subject,
                Queue     = c.get('run_queue', self.default_queue),
                Requestor = c['requestor'],
                Cc        = c.get('run_cc'),
                Text      = text or ""      ))

        # Open the ticket, or we'll not find it again.
        self.tracker.edit_ticket(ticket_id, Status='open')
        return ticket_id, True

    def search_run_ticket(self, run_id):
        """Search for a ticket referencing this run, and return the ticket number,
           as an integer, or return None if there is no such ticket.
        """
        c = self._config
        if not c:
            #In dummy mode, all tickets are 999
            return 999

        # Note - if the tickets aren't opened then 'new' tickets will just pile up in RT,
        # but I don't think that should happen.
        tickets = self.tracker.search( Queue = c.get('run_queue', self.default_queue),
                                       Subject__like = '%{}%'.format(run_id),
                                       Status = 'open'
                                     )

        if not list(tickets):
            return None

        tid = max([ int(t.get('id').strip('ticket/')) for t in tickets ])

        if len(tickets) > 1:
            # Should use really use proper logging here
            print("Warning: We have {} open tickets for run {}! Using the latest, {}".format(
                                    len(tickets),           run_id,               tid), file=sys.stderr)

        #Failing that...
        return tid if tid > 0 else None

    def reply_to_ticket(self, ticket_id, message, subject=None):
        """Sends a reply to the ticket.
        """
        if subject:
            #The rest API does not support supplying a subject, but I can maybe
            #hack around this? No, not easily.
            raise NotImplementedError("RT REST API does not support setting subjects on replies.")

        # Dummy connection mode...
        if not self._config: return True

        return self.tracker.reply(ticket_id, text=message)

    def comment_on_ticket(self, ticket_id, message, subject=None):

        if subject:
            #The rest API does not support supplying a subject, but I can maybe
            #hack around this? No, not easily.
            raise NotImplementedError("RT REST API does not support setting subjects on replies.")

        # Dummy connection mode...
        if not self._config: return True

        return self.tracker.comment(ticket_id, text=message)

    def change_ticket_status(self, ticket_id, status):
        # Dummy connection mode...
        if not self._config: return

        kwargs = dict( Status = status )
        try:
            return self.tracker.edit_ticket(ticket_id, **kwargs)
        except IndexError:
            pass # if the status is the same getting this exception

    def change_ticket_subject(self, ticket_id, subject):
        """You can reply to a ticket with a one-off subject, but not via the
           REST interface, which fundamentally does not support this.
           (see share/html/REST/1.0/Forms/ticket/comment in the RT source code)
           This call permanently changes the ticket subject.
        """
        # Dummy connection mode...
        if not self._config: return

        #why the extra space?? I'm not sure but it looks to have been added deliberately.
        kwargs = dict( Subject = "{} ".format(subject) )
        try:
            return self.tracker.edit_ticket(ticket_id, **kwargs)
        except IndexError:
            pass # if the subject is the same getting this exception

