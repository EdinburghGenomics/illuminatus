#!/usr/bin/env python3
import os, sys, re
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from contextlib import suppress
import configparser
from rt import Rt, AuthorizationError

# This was copied and modified from illuminatus/rt_runticket_manager.py to smrtino
# and then copied back to bring the two into line.
# I'm pretty sure that:
# 1) The RTUtils.py library is no use outside this script (so I just merged them).
# 2) This whole script is now generic enough to be shared (and thus moved to the toolbox). But
#    I've not (quite) done that yet.

def resolve_msg(in_val):
    """Replies and comments can be a literal string or "@./file" or "@-"
       This function resolves them.
    """
    #Deal with None/""
    if not in_val:
        return None

    if in_val == "@-":
        return sys.stdin.read()
    elif in_val.startswith("@"):
        with open(in_val[1:]) as in_file:
            return in_file.read()
    else:
        return in_val

def main(args):

    run_id = args.run_id # eg. "r54041_20180518_115257" or "180807_A00291_0056_AHCFLYDMXX"
    subject_postfix = args.subject
    ticket_status = args.status

    # Load the messages
    reply_message = resolve_msg(args.reply)
    comment_message = resolve_msg(args.comment)

    # If there is no action, we just want to check the ticket (never create it)
    check_only = not any([reply_message, comment_message, ticket_status, subject_postfix])

    # Determine subject for new ticket or else change of subject.
    if subject_postfix:
        subject = "Run %s : %s" % (run_id, subject_postfix)
    else:
        subject = "Run %s" % (run_id)

    rt_config_name = 'test-rt' if args.test else os.environ.get('RT_SYSTEM', 'production-rt')
    with RTManager( config_name = rt_config_name,
                    queue_setting = args.queue ) as rtm:

        if check_only:
            ticket_id, ticket_dict = rtm.search_run_ticket(run_id)
            if ticket_id:
                exit("Ticket #{} for '{}' has subject: {}".format(ticket_id, run_id, ticket_dict.get('Subject')))
            else:
                exit("No open ticket found for '{}'".format(run_id))

        # Or we can explicitly ask never to open a new ticket
        if args.no_create:
            ticket_id, ticket_dict = rtm.search_run_ticket(run_id)
            if ticket_id:
                created = False
            else:
                exit("No open ticket found for '{}'".format(run_id))
        else:
            # if the ticket does not exist, create it with the supplied message, be
            # that a commet or a reply, else if it does exits just get the ID
            ticket_id, created = rtm.find_or_create_run_ticket( run_id , subject, (reply_message or comment_message) )

        print("{} ticket_id is {}".format('New' if created else 'Existing', ticket_id))

        # change Subject of ticket
        # Note that it is valid to pass --subject "" to clear the postfix
        if not ( created or subject_postfix is None ):
            rtm.change_ticket_subject( ticket_id , subject )

        # reply to the ticket.
        # Not if the ticket was created, as the message will already be in the blurb.
        if reply_message and not created:
            rtm.reply_to_ticket( ticket_id , reply_message )

        # comment on the ticket
        # if the ticket was just created with only this comment then there is no
        # need to add it again
        if comment_message and not (created and not reply_message):
            rtm.comment_on_ticket( ticket_id , comment_message )

        # change status of a ticket
        if ticket_status:
            rtm.change_ticket_status( ticket_id , ticket_status )

# This part was modified from illuminatus/RTUtils.py.

class RTManager():
    def __init__(self, config_name, queue_setting):
        """Communication with RT is managed via the RT module.
           This wrapper picks up connection params from an .ini file,
           which must exist before you can even instatiate the object.

           To actually connect, either call connect() explicitly or say:
             with RTManager('test-rt') as rt_conn:
                ...
           to connect implicitly.
        """
        self._config_name = config_name
        self._queue_setting = queue_setting # eg. pbrun, run
        if config_name.lower() == 'none':
            # Special case for short-circuiting RT entirely, whatever the .ini
            # file says.
            self._config = None
        else:
            self._config = self._get_config_from_ini(config_name)

        self.tracker = None

    def connect(self, timeout=60):

        if not self._config:
            print("Making dummy connection - all operations will be no-ops.", file=sys.stderr)
            return self

        self.server_path = self._config['server']
        self.username, self.password = self._config['user'], self._config['pass']
        self._queue = self._config[self._queue_setting + '_queue']

        self.tracker = Rt( '/'.join([self.server_path, 'REST', '1.0']),
                           self.username,
                           self.password,
                           default_queue = self._queue )

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

    # Allow us to use this in a 'with' clause.
    def __enter__(self):
        return self.connect()
    def __exit__(self, *exc):
        # Can you logout of RT? Do you want to?
        pass

    def _get_config_from_ini(self, section_name):

        # Either read the config pointed to by RT_SETTINGS or else the default.
        # Don't attempt to read both, even though ConfigParser supports it.
        file_name = os.environ.get('RT_SETTINGS')
        file_name = file_name or os.path.join(os.path.expanduser('~'), '.rt_settings')

        cp = configparser.ConfigParser()
        if not cp.read(file_name):
            raise AuthorizationError('unable to read configuration file {file_name}'.format(**locals()))

        # A little validation
        if section_name not in cp:
            raise AuthorizationError('file {file_name} contains no configuration section {section_name}'.format(**locals()))

        conf_section = cp[section_name]

        # A little more validation
        for x in ['server', 'user', 'pass', self._queue_setting + '_queue']:
            if not conf_section.get(x):
                raise AuthorizationError('file {file_name} did not contain setting {x} needed for RT authentication'.format(**locals()))

        return conf_section


    # Added for illuminatus, adapted for SMRTino
    def find_or_create_run_ticket(self, run_id, subject, text=None):
        """Create a ticket for run if it does not exist already.
           If text is specified it will be used as the request blurb for
           the new ticket but if the ticket already existed it will be
           ignored.
           Returns a pair (ticket_id, created?).
        """
        c = self._config
        ticket_id, _ = self.search_run_ticket(run_id)

        if ticket_id:
            return ticket_id, False

        # Since dummy mode returns 999, if ticket_id was unset we can infer we have a real
        # connection and proceed with real ops.

        # Text munge
        text = re.sub(r'\n', r'\n      ', text.rstrip()) if text \
               else ""

        ticket_id = int(self.tracker.create_ticket(
                Subject   = subject,
                Queue     = self._queue,
                Requestor = c['requestor'],
                Cc        = c.get(self._queue_setting + '_cc') or "",
                Text      = text or ""      ))

        # Open the ticket, or we'll not find it again.
        self.tracker.edit_ticket(ticket_id, Status='open')
        return ticket_id, True

    def search_run_ticket(self, run_id):
        """Search for a ticket referencing this run, and return the ticket number,
           as an integer, along with the ticket metadata as a dict,
           or return (None, None) if there is no such ticket.
        """
        c = self._config
        if not c:
            #In dummy mode, all tickets are 999
            return (999, dict())

        # Note - if the tickets aren't opened then 'new' tickets will just pile up in RT,
        # but I don't think that should happen.
        tickets = list(self.tracker.search( Queue = self._queue,
                                            Subject__like = '%{}%'.format(run_id),
                                            Status = 'open'
                                          ))

        if not tickets:
            return (None, None)

        # Order the tickets by tid and get the highest one
        def get_id(t): return int(t.get('id').strip('ticket/'))
        tickets.sort(key=get_id, reverse=True)
        tid = get_id(tickets[0])

        if len(tickets) > 1:
            # Should use really use proper logging here
            print("Warning: We have {} open tickets for run {}! Using the latest, {}".format(
                                    len(tickets),           run_id,               tid), file=sys.stderr)

        #Failing that...
        return (tid, tickets[0]) if tid > 0 else (None, None)

    def reply_to_ticket(self, ticket_id, message, subject=None):
        """Sends a reply to the ticket.
        """
        if subject:
            # The rest API does not support supplying a subject, but I can maybe
            # hack around this? No, not easily.
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
        # Ignore IndexError raised when subject is already set
        with suppress(IndexError):
            self.tracker.edit_ticket(ticket_id, **kwargs)

    def change_ticket_subject(self, ticket_id, subject):
        """You can reply to a ticket with a one-off subject, but not via the
           REST interface, which fundamentally does not support this.
           (see share/html/REST/1.0/Forms/ticket/comment in the RT source code)
           This call permanently changes the ticket subject.
        """
        # Dummy connection mode...
        if not self._config: return

        # why the extra space?? I'm not sure but it looks to have been added deliberately.
        kwargs = dict( Subject = "{} ".format(subject) )

        # Ignore IndexError raised when subject is already set
        with suppress(IndexError):
            self.tracker.edit_ticket(ticket_id, **kwargs)

def parse_args(*args):
    description = """This script allows you to manipulate a ticket for an instrument run.
                     You can reply, comment, open, stall, resolve tickets.
                     Replying or commenting on a closed or non-existent ticket will create a new one,
                     unless you specify --no-create.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("-r", "--run_id", required=True,
                            help="The run id of the ticket.")
    argparser.add_argument("-Q", "--queue", required=True,
                            help="The queue to use. A name defined in rt_settings.ini as FOO_queue,"
                                 " not a literal queue name.")
    argparser.add_argument("--reply",
                            help="Post reply message to the ticket. " +
                                 "Use @foo.txt to read the message from file foo.txt.")
    argparser.add_argument("--comment",
                            help="Post comment message to the ticket" +
                                 "Use @foo.txt to read the message from file foo.txt.")
    argparser.add_argument("--subject",
                            help="Change the ticket subject (postfix)")
    argparser.add_argument("--status",
                            help="Change status of the ticket")
    argparser.add_argument("--no_create", action="store_true",
                            help="Avoid creating new tickets.")
    argparser.add_argument("--test", action="store_true",
                            help="Set the script to connect to test-rt (as defined in rt_settings.ini)")

    return argparser.parse_args(*args)


if __name__ == "__main__":
    main(parse_args())
