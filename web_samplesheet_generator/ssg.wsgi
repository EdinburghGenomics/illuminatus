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
    """There is a recipe for serving up CSV in the Falcon docs
    """
    def on_get(self, req, resp):
        # Work out which submit button was clicked. We're encoding the FCID in the
        # button name.
        try:
            fcid, = [ p[len("submit_"):] for p in req.params if p.startswith("submit_") ]
        except ValueError:
            raise falcon.HTTPBadRequest(title="FCID not set in params") from None

        try:
            run = ragic.get_run(fcid, add_samples=True, rc=rc)
            ss_lines = gen_ss(run)
        except Exception as e:
            # Problems here should be reported to the user
            raise falcon.HTTPInternalServerError(title=f"Failed to generate a SampleSheet - {e}")

        # Include both the fcid and the experiment name in the filename.
        experiment = run.get("Experiment", "Kxxx")

        resp.content_type = 'text/csv'
        resp.downloadable_as = f"{experiment}_{fcid}_SampleSheet.csv"
        resp.text = "\n".join(ss_lines) + "\n"

        L.info("Serving file {resp.downloadable_as} with {len(ss_lines)} lines.")

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

                if os.environ.get('WSGI_SINGLE_REQUEST', '0') == '0':
                    httpd.serve_forever()
                else:
                    # Or for a very dirty forced reload (for local testing only):
                    httpd.timeout = 10
                    httpd.handle_request()
                break
        except OSError:
            L.debug(f"Port {port} is in use; trying the next one.")
            continue
        except KeyboardInterrupt:
            L.info("Quitting.")
            break

