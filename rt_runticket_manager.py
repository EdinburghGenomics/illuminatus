#!/usr/bin/env python3
import sys
from argparse import ArgumentParser

from illuminatus.rt_utils import RT_manager


def parse_args():
    description = """This script allows you to manipulate a ticket for a particular run.
    You can reply, comment, open, stall, resolve tickets.
    """
    argparser = ArgumentParser(description=description)
    argparser.add_argument("-r", "--run_id", dest="run_id", required=True,
                            help="The run id of the ticket.")
    argparser.add_argument("--reply", dest="reply_message",
                            help="Set reply message for the ticket")
    argparser.add_argument("--comment", dest="comment_message",
                            help="Set comment message for the ticket")
    argparser.add_argument("--subject", dest="subject", default="",
                            help="Set ticket subject (postfix)")
    argparser.add_argument("--status", dest="ticket_status",
                            help="Set status of the ticket")
    argparser.add_argument("--test", dest="test", action="store_true", default=True,
                            help="Set the script to create ticket on rt-test")

    return argparser.parse_args()

def main(args):

    run_id = args.run_id # eg. "161004_K00166_0134_AHFJJ5BBXX"
    reply_message = args.reply_message
    comment_message = args.comment_message
    subject_postfix = args.subject
    ticket_status = args.ticket_status

    rt_manager = RT_manager( test = args.test )
    subject = "[Run %s] %s" % (run_id , subject_postfix)

    # get a ticket id for the run
    ticket_id = rt_manager.find_or_create_run_ticket( run_id , subject )
    print("ticket_id is {}".format(ticket_id))

    # change Subject of ticket
    # ??? is this the subject of the ticket or the subject of this reply?
    if args.subject:
        rt_manager.change_ticket_subject ( ticket_id , subject )
        
    # reply to the ticket
    if reply_message:
        rt_manager.reply_to_ticket( ticket_id , reply_message )

    # comment on the ticket
    if comment_message:
        rt_manager.comment_on_ticket( ticket_id , comment_message )

    # change status of a ticket
    if ticket_status:
        rt_manager.change_ticket_status( ticket_id , ticket_status )

if __name__ == "__main__":
    main(parse_args())
