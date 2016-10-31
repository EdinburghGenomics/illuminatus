'''
Created on 30 Apr 2013

@author: tcezard
'''
import os
import logging
import re

import rt
from rt import AuthorizationError, InvalidUse






# Servers
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



class Rt_manager():
    def __init__(self, test=False):
        self.tracker = self._get_RT_connection(test)

    def _get_RT_server(self, test=False):
        """specify the server name"""
        if test:
            return RT_TEST_SERVER
        else:
            return RT_SERVER


    def _get_username_and_password(self):
        """Catch the username and password to be used to login from a file in .rt_pass"""
        file_name = os.path.join(os.path.expanduser('~'), '.rt_pass')
        if os.path.exists(file_name):
            with open(file_name) as open_file:
                data = open_file.read()
            if data:
                username, password = data.strip().split()
                return username, password
            else:
                AuthorizationError('file %s did not contain RT authentication' % file_name)
        else:
            raise AuthorizationError('file %s containing RT authentication was not found' % file_name)


    def _get_RT_connection(self, test=False):
        server_path = self._get_RT_server(test)
        username, password = self._get_username_and_password()
        path = os.path.join(server_path, 'REST', '1.0')
        tracker = rt.Rt(path, username, password, default_queue=DEFAULT_QUEUE)
        tracker.login()
        return tracker

    """
    Added for illuminatus
    """
    def find_or_create_run_ticket(self, run_id, subject ):
        """Create a ticket for run only if it does not exist already"""
        ticket_id = self.search_run_ticket(run_id)
        if not ticket_id or int(ticket_id) < 1:
            text = ""
            kwargs = {"Subject": subject }
            kwargs["Queue"] = RUN_QUEUE
            kwargs["Requestor"] = RUN_REQUESTOR
            kwargs["Cc"] = RUN_CC
            kwargs["Text"] = text
            ticket_id = self.tracker.create_ticket(**kwargs)
        return ticket_id

    def search_run_ticket(self, run_id):
        tickets = self.tracker.search(Queue=RUN_QUEUE)
        valid_ticket = []
        for ticket in tickets:
            if run_id in ticket.get('Subject'):
                valid_ticket.append(ticket)
        if valid_ticket and len(valid_ticket) == 1:
            return valid_ticket[0].get('id').strip('ticket/')
        elif not valid_ticket:
            return None
        else:
            raise InvalidUse("More than one open ticket for run %s" % run_id)

    def reply_to_ticket(self, ticket_id, message):
        return self.tracker.reply(ticket_id, text=message )

    def comment_on_ticket(self, ticket_id, message):
        return self.tracker.comment(ticket_id, text=message)

    def change_ticket_status(self, ticket_id, status):
        kwargs = {"Status": status}
        try:
            return self.tracker.edit_ticket(ticket_id, **kwargs)
        except IndexError:
            pass # if the status is the same getting this exception

    def change_ticket_subject(self, ticket_id, subject):
        kwargs = {"Subject": "%s " % (subject)}
        try:
            return self.tracker.edit_ticket(ticket_id, **kwargs)
        except IndexError:
            pass # if the subject is the same getting this exception

