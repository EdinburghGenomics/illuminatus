#!/usr/bin/env python3
import sys, os
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from illuminatus.RTUtils import RT_manager


def parse_args():
    description = """This script allows you to manipulate a ticket for a particular run.
    You can reply, comment, open, stall, resolve tickets.
    """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("-r", "--run_id", required=True,
                            help="The run id of the ticket.")
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
    argparser.add_argument("--test", action="store_true",
                            help="Set the script to connect to test-rt (as defined in rt_settings.ini)")

    return argparser.parse_args()

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

    run_id = args.run_id # eg. "161004_K00166_0134_AHFJJ5BBXX"
    subject_postfix = args.subject
    ticket_status = args.status

    reply_message = resolve_msg(args.reply)
    comment_message = resolve_msg(args.comment)

    #Determine subject for new ticket or else change of subject.
    if subject_postfix:
        subject = "Run %s : %s" % (run_id, subject_postfix)
    else:
        subject = "Run %s" % (run_id)

    with RT_manager( 'test-rt' if args.test else
                     os.environ.get('RT_SYSTEM', 'production-rt') ) as rtm:

        # if the ticket does not exist, create it with the supplied message, be
        # that a commet or a reply
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

if __name__ == "__main__":
    main(parse_args())
