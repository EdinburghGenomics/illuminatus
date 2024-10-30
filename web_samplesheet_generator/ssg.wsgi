# vim: ft=python
"""A skeleton for the real sample sheet generator.

   This will serve either an HTML page or a CSV file. You can run this directly
   under Python if you want to test it.
"""
import os, sys, re
import falcon
import chevron
import logging as L

# Get the path of this file
base_dir = os.path.abspath(os.path.dirname(__file__))

# This might need some sys.path tinkering...
from unittest.mock import patch
with patch('sys.path', new=[f"{base_dir}/.."] + sys.path):
    from samplesheet_from_ragic import ragic, gen_ss, illuminatus_version

def app_map():
    return (("/",         MainPageHandler),
            ("/getsheet", GenCSVHandler),
            ("/version",  VersionHandler), )

# We want a single global ragic client, not re-reading the config for every page served
rc = None

class VersionHandler:
    def on_get(self, req, resp):
        # Set 'media' to serve JSON
        resp.media = dict(version = illuminatus_version)

class MainPageHandler:
    """Serve the HTML page.
    """
    runs_to_fetch = 12

    def render(self, run_list):
        """Load the template and render it.
        """
        # TODO - run list to items

        template_file = os.path.join(base_dir, "ssg.html.tmpl")
        context = dict( page_title = "Generate a sample sheet from Ragic!",
                        max_rows = self.runs_to_fetch )

        context['table_rows'] = [ dict( date = r.get("Last Update"),
                                        fcid = r.get("Flowcell ID"),
                                        expt = r.get("Experiment"),
                                        project = " ".join(r.get("Project")) )
                                  for r in run_list.values() ]

        with open(template_file) as tfh:
            return chevron.render(tfh, context)

    def on_get(self, req, resp):
        """Get the last 12 runs from Ragic
        """
        recent_runs = rc.list_entries( "Illumina Run",
                                       latest_n = self.runs_to_fetch,
                                       subtables = False )

        resp.content_type = falcon.MEDIA_HTML
        resp.text = self.render(recent_runs)

class GenCSVHandler:
    """There is a recipe for this in the Falcon docs
    """
    def on_get(self, req, resp):
        csv_string = 'head1,head2,head3\nval1,"val2",3\n'

        resp.content_type = 'text/csv'
        resp.downloadable_as = 'not_a_sample_sheet.csv'
        resp.text = csv_string

# Start the logging
log_level = L.DEBUG if (__name__ == '__main__' or os.environ.get('DEBUG', '0') != '0') else L.INFO
L.basicConfig(format='{levelname:s}: {message:s}', level=log_level, style='{')

# Construct the App
app = falcon.App()
for apath, ahandler in app_map():
    app.add_route(apath, ahandler())

# Connect to the Ragic
rc = ragic.RagicClient.connect_with_creds()
rc.add_forms(ragic.forms)

# This makes it work in Apache.
application = app

if __name__ == '__main__':
    # Serve the app
    from wsgiref.simple_server import make_server

    # Find a port between 8080 and 8099
    for port in range(8080, 8100):
        try:
            with make_server('127.0.0.1', port, app) as httpd:
                L.info(f"Serving on http://localhost:{port}")

                httpd.serve_forever()
                break
        except OSError:
            L.debug(f"Port {port} is in use; trying the next one.")
            continue
        except KeyboardInterrupt:
            L.info("Quitting.")
            break

