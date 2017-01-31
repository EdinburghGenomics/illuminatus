#!/usr/bin/env python3
import sys
from argparse import ArgumentParser

from illuminatus.RTUtils import RT_manager


def parse_args():
    description = """This script allows you to manipulate a ticket for a particular run.
    You can reply, comment, open, stall, resolve tickets.
    """
    argparser = ArgumentParser(description=description)
    argparser.add_argument("-r", "--run_id", required=True,
                            help="The run id of the ticket.")
    argparser.add_argument("--reply",
                            help="Post reply message to the ticket")
    argparser.add_argument("--comment",
                            help="Post comment message to the ticket")
    argparser.add_argument("--subject",
                            help="Use this subject for your comment or reply")
    argparser.add_argument("--change_subject",
                            help="Change the ticket subject (postfix)")
    argparser.add_argument("--change_status",
                            help="Change status of the ticket")
    argparser.add_argument("--test", action="store_true",
                            help="Set the script to connect to test-rt (as defined in rt_settings.ini)")

    return argparser.parse_args()

def main(args):

    run_id = args.run_id # eg. "161004_K00166_0134_AHFJJ5BBXX"
    reply_message = args.reply
    comment_message = args.comment
    reply_subject = args.subject
    subject_postfix = args.change_subject
    ticket_status = args.change_status

    #Determine subject for new ticket or else change of subject.
    if subject_postfix:
        subject = "Run %s : %s" % (run_id, subject_postfix)
    else:
        subject = "Run %s" % (run_id)

    #Determine subject for just this reply
    extra_args = dict()
    if reply_subject:
        extra_args['Subject'] = reply_subject

    with RT_manager( 'test-rt' if args.test else 'production-rt' ) as rtm:

        # get a ticket id for the run
        ticket_id = rtm.find_or_create_run_ticket( run_id , subject )
        print("ticket_id is {}".format(ticket_id))

        # permanently change Subject of ticket
        # Note that it is valid to pass --subject "" to clear the postfix
        if subject_postfix is not None:
            rtm.change_ticket_subject( ticket_id , subject )

        # reply to the ticket
        if reply_message:
            rtm.reply_to_ticket( ticket_id , reply_message, **extra_args )

        # comment on the ticket
        if comment_message:
            rtm.comment_on_ticket( ticket_id , comment_message, **extra_args )

        # change status of a ticket
        if ticket_status:
            rtm.change_ticket_status( ticket_id , ticket_status )

if __name__ == "__main__":
    main(parse_args())
