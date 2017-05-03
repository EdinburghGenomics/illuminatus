#!/usr/bin/env python3

"""Basic LIMS querying code for the things we need in Illuminatus.
   Generic LIMS functionality should be folded back into the genelogics project
   https://github.com/EdinburghGenomics/genologics/blob/master/examples/get_projects.py

   This module will contact the LIMS in various ways (API login, direct SQL, CIFS share).
   The idea is that the user should be able to set connection parameters in
   ~/.genologicsrc or equivalent and then just rely on this module to do the best
   thing.
"""
import os
import configparser

import psycopg2
from psycopg2.extras import NamedTupleCursor
from psycopg2.extensions import adapt

#from genologics.lims import Lims

def main():
    """Basic test.
    """
    lims = MyLims()
    print("Project 10657 is {}".format(*lims.get_project_names(10657)))

    # Get the real name of project 10657 (_Nussey_Daniel)
    print("Project 10657 is {}".format(*get_project_names(10657)))

def get_project_names(*proj_nums):
    """Given a list of project numbers, return a corresponding
       list of full names.

       This version uses the direct SQL query.
    """
    res = []
    with MyLimsDB() as ldb:
        for pn in proj_nums:
            qres = ldb.select("SELECT name FROM project WHERE name LIKE %s || '_%%'", pn)

            if len(qres) > 1:
                raise LookupError("More than one project found with prefix %s", pn)
            else:
                res.append(qres[0].name if qres else None)

    return res


class MyLimsDB:
    """ Taken from BasicPGConn which was my initial stab at this, but now
        connects according to the .genoligcsrc file.
        Basic connector for basic one-at-a-time SELECT statements.
        usage:
            with MyLimsDB() as mydb:
                res1 = mydb.select("SELECT 1,2,3")
                #Safe query...
                res2 = mydb.select("SELECT * FROM sample WHERE name = %s", 'Bobby')
                #Unsafe query...
                res_bad = mydb.select("SELECT * FROM sample WHERE name = '%s'" % 'Bobby')
    """

    def __init__(self):
        """Connect using the info in ~/.genologics or equivalent.
        """
        self._conn_str = "user={} host={} dbname={}".format(
                            *get_config("genologics-sql", "USERNAME SERVER DATABASE".split()) )
        self._conn = None

    def is_connected(self):
        return bool(self._conn)

    def connect(self):
        self._conn = psycopg2.connect(self._conn_str)
        return self._conn

    def close(self):
        self._conn.close()

    def select(self, query, *pps):
        """Executes a query and fetches the data. We assume it's a
           SELECT query or equivalent. Parameters must be positional.
        """
        #Docs say one cursor per query is best for things like this.
        cur = self._conn.cursor(cursor_factory=NamedTupleCursor)

        cur.execute(query, pps)
        res = cur.fetchall()
        cur.close()

        return res

    #Things that make the 'with' syntax work...
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc_info):
        self.close()

class MyLims:

    def __init__(self):
        self.lims = Lims(*get_config())
        self.lims.check_version()

    def get_project_names_slow(self, *proj_nums):
        # Get the list of all projects.
        projects = self.lims.get_projects()
        print('{} projects in total'.format(len(projects)))

        # Unfortunately this doesn't work...
        # projects = lims.get_projects(name="10657_%")
        # and calling .name on every project is slow as it entails an extra GET
        # Maybe we need to bypass Clarity and hit PostgreSQL?

        #Yes I'm scanning the list many times, but the key thing is I only fetch it once.
        res = []
        for p_num in proj_nums:
            p_prefix = str(p_num) + '_'
            p_name = None
            for proj in projects:
                if proj.name.startswith(p_prefix):
                    if p_name:
                        raise LookupError("More than one project found with prefix " + p_prefix)
                    else:
                        p_name = proj.name
            res.append(p_name)

        return res

    def get_project_names(self, *proj_nums):
        #Quickly get the list of all project names.
        lims = self.lims
        projects = []

        proot = lims.get(lims.get_uri('projects'))
        while True:  # Loop over all pages.
            for node in proot.findall('.//name'):
                projects.append(node.text)
            next_page = proot.find('next-page')
            if next_page is None: break
            proot = self.get(next_page.attrib['uri'])

        #Yes I'm scanning the list many times, but the key thing is I only fetch it once.
        res = []
        for p_num in proj_nums:
            p_prefix = str(p_num) + '_'
            p_name = None
            for proj in projects:
                if proj.startswith(p_prefix):
                    if p_name:
                        raise LookupError("More than one project found with prefix " + p_prefix)
                    else:
                        p_name = proj
            res.append(p_name)

        return res

def get_config(section='genologics', parts=['BASEURI', 'USERNAME', 'PASSWORD']):
    """The genologics.config module is braindead and broken.
       Here's a simplistic reimplementation.
    """
    config = configparser.SafeConfigParser()
    conf_file = config.read(os.environ.get('GENOLOGICSRC',
                            [os.path.expanduser('~/.genologicsrc'),
                             'genologics.conf', 'genologics.cfg', '/etc/genologics.conf'] ))

    return [config[section][i] for i in parts]

if __name__ == '__main__':
    main()
