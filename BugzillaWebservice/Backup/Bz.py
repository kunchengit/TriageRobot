#!/usr/bin/env python

"""
Portions of this code taken from the testopia bugzilla interface (see
license below). Other portions of this code taken from reviewboard
- jon@vmware.com

The contents of this file are subject to the Mozilla Public
License Version 1.1 (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of
the License at http://www.mozilla.org/MPL/

Software distributed under the License is distributed on an "AS
IS" basis, WITHOUT WARRANTY OF ANY KIND, either express or
implied. See the License for the specific language governing
rights and limitations under the License.

The Original Code is the Bugzilla Testopia Python API Driver.

The Initial Developer of the Original Code is Airald Hapairai.
Portions created by Airald Hapairai are Copyright (C) 2008
Novell. All Rights Reserved.
Portions created by David Malcolm are Copyright (C) 2008 Red Hat.
All Rights Reserved.
Portions created by Will Woods are Copyright (C) 2008 Red Hat.
All Rights Reserved.
Portions created by Bill Peck are Copyright (C) 2008 Red Hat.
All Rights Reserved.

Contributor(s): Airald Hapairai
  David Malcolm <dmalcolm@redhat.com>
  Will Woods <wwoods@redhat.com>
  Bill Peck <bpeck@redhat.com>

The CookieTransport class is by Will Woods, based on code in
Python's xmlrpclib.Transport, which has this copyright notice:

# The XML-RPC client interface is
#
# Copyright (c) 1999-2002 by Secret Labs AB
# Copyright (c) 1999-2002 by Fredrik Lundh
#
# By obtaining, using, and/or copying this software and/or its
# associated documentation, you agree that you have read, understood,
# and will comply with the following terms and conditions:
#
# Permission to use, copy, modify, and distribute this software and
# its associated documentation for any purpose and without fee is
# hereby granted, provided that the above copyright notice appears in
# all copies, and that both that copyright notice and this permission
# notice appear in supporting documentation, and that the name of
# Secret Labs AB or the author not be used in advertising or publicity
# pertaining to distribution of the software without specific, written
# prior permission.
#
# SECRET LABS AB AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD
# TO THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANT-
# ABILITY AND FITNESS.  IN NO EVENT SHALL SECRET LABS AB OR THE AUTHOR
# BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY
# DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
# WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS
# ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.
"""
import sys

#
# check for recent python; older versions don't have the right cookielib and
# xmlrpclib
#

version = sys.version_info
if not ( version[0] >= 2 and version [1] >= 5 ):
    print "bz.py requires python >= 2.5. Please use the python from the bldmnt systems or upgrade your current installation."
    sys.exit(1);


import xmlrpclib, urllib2, cookielib, os, getpass, sys
import pprint
from types import *
from datetime import datetime, time
from urlparse import urljoin, urlparse
from cookielib import CookieJar
from optparse import OptionParser
from operator import itemgetter

BUGZILLA_URL = 'https://bugzilla.eng.vmware.com/xmlrpc.cgi'
DEBUG = False
VERSION = "0.1"

options = None

class CookieTransport(xmlrpclib.Transport):
    '''A subclass of xmlrpclib.Transport that supports cookies.'''
    cookiejar = None
    scheme = 'https'

    def cookiefile(self):
        if 'USERPROFILE' in os.environ:
            homepath = os.path.join(os.environ["USERPROFILE"], "Local Settings",
            "Application Data")
        elif 'HOME' in os.environ:
            homepath = os.environ["HOME"]
        else:
            homepath = ''

        cookiefile = os.path.join(homepath, ".bugzilla-cookies.txt")
        return cookiefile

    # Cribbed from xmlrpclib.Transport.send_user_agent
    def send_cookies(self, connection, cookie_request):
        if self.cookiejar is None:
            self.cookiejar = cookielib.MozillaCookieJar(self.cookiefile())

            if os.path.exists(self.cookiefile()):
                self.cookiejar.load(self.cookiefile())
            else:
                self.cookiejar.save(self.cookiefile())

        # Let the cookiejar figure out what cookies are appropriate
        self.cookiejar.add_cookie_header(cookie_request)

        # Pull the cookie headers out of the request object...
        cookielist=list()
        for h,v in cookie_request.header_items():
            if h.startswith('Cookie'):
                cookielist.append([h,v])

        # ...and put them over the connection
        for h,v in cookielist:
            connection.putheader(h,v)



    # This is the same request() method from xmlrpclib.Transport,
    # with a couple additions noted below
    def request(self, host, handler, request_body, verbose=0):
        h = self.make_connection(host)
        if verbose:
            h.set_debuglevel(1)

        # ADDED: construct the URL and Request object for proper cookie handling
        request_url = "%s://%s/" % (self.scheme,host)
        cookie_request  = urllib2.Request(request_url)

        self.send_request(h,handler,request_body)
        self.send_host(h,host)
        self.send_cookies(h,cookie_request) # ADDED. creates cookiejar if None.
        self.send_user_agent(h)
        self.send_content(h,request_body)

        errcode, errmsg, headers = h.getreply()

        # ADDED: parse headers and get cookies here
        # fake a response object that we can fill with the headers above
        class CookieResponse:
            def __init__(self,headers): self.headers = headers
            def info(self): return self.headers
        cookie_response = CookieResponse(headers)
        # Okay, extract the cookies from the headers
        self.cookiejar.extract_cookies(cookie_response,cookie_request)
        # And write back any changes
        if hasattr(self.cookiejar,'save'):
            self.cookiejar.save(self.cookiejar.filename)

        if errcode != 200:
            raise xmlrpclib.ProtocolError(
                host + handler,
                errcode, errmsg,
                headers
                )

        self.verbose = verbose

        try:
            sock = h._conn.sock
        except AttributeError:
            sock = None

        return self._parse_response(h.getfile(), sock)

class SafeCookieTransport(xmlrpclib.SafeTransport,CookieTransport):
    '''SafeTransport subclass that supports cookies.'''
    scheme = 'https'
    request = CookieTransport.request

VERBOSE=0

class BugzillaServer(object):

    def __init__(self, url, cookie_file, options):
        self.url = url
        self.cookie_file = cookie_file
        self.options = options
        self.cookie_jar = cookielib.MozillaCookieJar(self.cookie_file)
        self.server = xmlrpclib.ServerProxy(url, SafeCookieTransport())
        self.columns = None

    def login(self):

        if self.has_valid_cookie():
            return

        print "==> Bugzilla Login Required"
        print "Enter username and password for Bugzilla at %s" % self.url
        username = raw_input('Username: ')
        password = getpass.getpass('Password: ')

        debug('Logging in with username "%s"' % username)
        try:
            self.server.User.login({"login" : username, "password" :
            password})
        except xmlrpclib.Fault, err:
            print "A fault occurred:"
            print "Fault code: %d" % err.faultCode
            print "Fault string: %s" % err.faultString
        debug("logged in")
        self.cookie_jar.save;

    def get_columns(self, filter):
        if self.columns is None:
            try:
                self.columns = self.server.Bug.get_columns(filter)
            except xmlrpclib.Fault, err:
                print "A fault occurred:"
                print "Fault code: %d" % err.faultCode
                print "Fault string: %s" % err.faultString
                sys.exit(1)
        return self.columns

    def saved_queries(self, user):
        try:
            self.queries = self.server.Search.get_all_saved_queries(user)
        except xmlrpclib.Fault, err:
                print "A fault occurred:"
                print "Fault code: %s" % err.faultCode
                print "Fault string: %s" % err.faultString
                sys.exit(1)
        for query in self.queries:
            print query
        sys.exit(0)

    def query(self, query):
        self.parse_columns('buglist')
        try:
            self.query = self.server.Search.run_saved_query(query[0],
            query[1], self.withcolumns)
        except xmlrpclib.Fault, err:
                print "A fault occurred:"
                print "Fault code: %s" % err.faultCode
                print "Fault string: %s" % err.faultString
                sys.exit(1)

        if self.withcolumns:
            # If columns were supplied we print out a pretty table
            header = "|"
            # Sort CLI-fed columns by fielddefs.sortkey
            sorted_columns = sorted(self.withcolumns.iteritems(),
                                    key=itemgetter(1))
            for column in map(itemgetter(0), sorted_columns):
                header = header + " %s |" % \
                self.query['columns'][column]['title'].ljust(self.query['maxsize'][column] + 1)

            print "_" * len(header)
            print header
            print "|" + "_" * (len(header) - 2) + "|"
            for bug in self.query['bugs']:
                row = '|'
                for column in map(itemgetter(0), sorted_columns):
                    value = ''
                    if bug.has_key(column):
                        if isinstance( bug[column], basestring):
                            if (len(bug[column]) > 60):
                                # deal with truncated values
                                bug[column] = bug[column][0:56] + "..."

                        value = " %.60s" % bug[column]
                    row = row + value.ljust(self.query['maxsize'][column] + 2) + " |"
                print row
            print "|" + "-" * (len(header) - 2) + "|"
        else:
            # no columns, just a list of bug ids
            for id in self.query['bugidlist']:
                print id

    def list_columns(self):
        columns = self.get_columns('buglist')
        print "_" * 52
        print "| %s| %s |" % ('Name'.ljust(20), 'Description'.ljust(26))
        print "|" + "-" * 50 + "|"
        for column in columns:
            print "| %s| %s |" % (column['name'].ljust(20), column['description'].ljust(26))
        print "|" + "-" * 50 + "|"

    def add_comment(self, bug_id, comment):
        try:
            self.server.Bug.add_comment(bug_id, comment)
        except xmlrpclib.Fault, err:
            print "A fault occurred:"
            print "Fault code: %d" % err.faultCode
            print "Fault string: %s" % err.faultString
            sys.exit(1)

        print "Comment added to bug %s" % bug_id

    def parse_columns(self, filter):
        self.withcolumns = {}
        self.nocolumns = {}

        if self.options.withcolumns is not None:
            for column in self.options.withcolumns.split(','):
                for all_col in self.get_columns(filter):
                    if column == all_col['name']:
                        self.withcolumns[column] = all_col['sortkey']

        if self.options.nocolumns is not None:
            for column in self.options.nocolumns.split(','):
                self.nocolumns[column] = 1

    def show_bug(self, bug_id):
        try:
            bug = self.server.Bug.show_bug(bug_id)
        except xmlrpclib.Fault, err:
            print "A fault occurred:"
            print "Fault code: %d" % err.faultCode
            print "Fault string: %s" % err.faultString
            sys.exit(1)

        columns = self.get_columns('bug')
        # list of fields where zero is a valid (non-empty) result
        zerofields = ('cf_attempted', 'cf_failed')
        # list of fields to convert time format
        timefields = ('delta_ts', 'creation_ts')
        for timefield in timefields:
            converted = datetime.strptime(bug[timefield].value,
            "%Y%m%dT%H:%M:%S")
            bug[timefield] = converted.strftime("%Y.%m.%d %H:%M:%S")

        self.parse_columns('bug')

        for column in columns:
            if self.options.nocolumns:
                if column['name'] in self.nocolumns:
                    continue

            if self.options.withcolumns:
                if column['name'] not in self.withcolumns:
                    continue

            if column['name'] == "comments":
                if (bug.has_key('comments') and
                    (self.options.comments or
                     (self.options.withcolumns and
                      "comments" not in self.withcolumns))):
                    for comment in bug['comments']:
                        print "\nOn %s %s wrote:\n%s"% (comment['time'],
                                                        comment['email'],
                                                        comment['body'])
            elif column['name'] == "description":
                print "Initial Description:\n%s\n" % bug['description']
            else:
                if ((bug[column['name']] and (bug[column['name']] != "---")) or
                ( column['name'] in zerofields and bug[column['name']] == 0)
                or self.options.empty):
                    print "%s: %s" % (column['description'], bug[column['name']])

    def has_valid_cookie(self):
        try:
            parsed_url = urlparse(self.url)
            host = parsed_url[1]
            path = parsed_url[2] or '/'

            # Cookie files don't store port numbers, unfortunately, so
            # get rid of the port number if it's present.
            host = host.split(":")[0]

            debug( "Looking for '%s' cookie in %s" % \
                  (host, self.cookie_file))
            self.cookie_jar.load(self.cookie_file, ignore_expires=True)

            try:
                cookie = self.cookie_jar._cookies[host]['/']['Bugzilla_logincookie']

                if not cookie.is_expired():
                    debug("Loaded valid cookie -- no login required")
                    return True

                debug("Cookie file loaded, but cookie has expired")
            except KeyError:
                debug("Cookie file loaded, but no cookie for this server")
        except IOError, error:
            debug("Couldn't load cookie file: %s" % error)

        return False


def parse_options(args):
    parser = OptionParser(usage="%prog [-l|q] [-bcde] [-w|n] [column names] \
    [-a] [comment] [bug_id]",
                          version="%prog " + VERSION)
    parser.add_option("-a", "--addcomment",
                      action="store", dest="comment", default=None,
                      help="add a comment to the given bug",
                      type="string")
    parser.add_option("-b", "--bugzillaurl",
                      action="store", dest="bugzilla_url",
                      default=BUGZILLA_URL,
                      help="full url to xmlrpc.cgi on bugzilla server",
                      type="string")
    parser.add_option("-c", "--comments",
                      action="store_true", dest="comments", default=None,
                      help="show comments")
    parser.add_option("-d", "--debug",
                      action="store_true", dest="debug", default=DEBUG,
                      help="display debug output")
    parser.add_option("-e", "--empty",
                      action="store_true", dest="empty", default=False,
                      help="show fields with empty values")
    parser.add_option("-q", "--query",
                      dest="query", type="string",
                      help="see a user's saved query", nargs=2)
    parser.add_option("-s", "--savedqueries",
                      dest="saved", type="string",
                      help="view all of a user's saved queries", nargs=1)
    parser.add_option("-l", "--listcolumns",
                      action="store_true", dest="listcolumns", default=False,
                      help="list available bug columns")
    parser.add_option("-n", "--nocolumns",
                      action="store", dest="nocolumns", default=None,
                      help="comma-separated list of columns not to display",
                      type="string")
    parser.add_option("-w", "--withcolumns",
                      action="store", dest="withcolumns", default=None,
                      help="comma-separated list of columns to display",
                      type="string")

    (globals()["options"], args) = parser.parse_args(args)
    return args

def debug(s):
    """
    Prints debugging information if run with --debug
    """
    if DEBUG or options and options.debug:
        print ">>> %s" % s

def main(args):
    if 'USERPROFILE' in os.environ:
        homepath = os.path.join(os.environ["USERPROFILE"], "Local Settings",
                                "Application Data")
    elif 'HOME' in os.environ:
        homepath = os.environ["HOME"]
    else:
        homepath = ''

    cookie_file = os.path.join(homepath, ".bugzilla-cookies.txt")

    args = parse_options(args)
    bugzilla_url = options.bugzilla_url

    server = BugzillaServer(bugzilla_url, cookie_file, options)
    server.login()

    if (options.saved):
        server.saved_queries(options.saved)
        sys.exit(0)

    if (options.query):
        server.query(options.query)
        sys.exit(0)

    if (options.listcolumns):
        server.list_columns()
        sys.exit(0)

    if len(args) < 1:
        print "You must specify a bug number"
        sys.exit(1)

    bug_id = args[0]

    if (options.comment):
        server.add_comment(bug_id, options.comment)
        sys.exit(0)

    if (options.withcolumns and options.nocolumns):
        print "--nocolumns and --withcolumns are mutually exclusive"
        sys.exit(1)

    bug = server.show_bug(bug_id)

if __name__ == "__main__":
    main(sys.argv[1:])
