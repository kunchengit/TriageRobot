import xmlrpclib, urllib2, cookielib, os
from urlparse import urlparse
BUGZILLA_URL = "https://bugzilla.eng.vmware.com/xmlrpc.cgi"
DEBUG = 1

class CookieTransport(xmlrpclib.Transport):
    """A subclass of xmlrpclib.Transport that supports cookies."""
    cookiejar = None
    scheme = 'https'
    def cookiefile(self):
        #cookiefile = "metric_tool/Tool/bugzilla-cookies.txt"
        cur_path = os.path.dirname(os.path.realpath(__file__))
        cookiefile = cur_path + "/bugzilla-cookies.txt"
        return cookiefile

    def _parse_response(self, responsefile, sock=None):
        """Code copied from pythong 2.6 lib."""
        # read response from input file/socket, and parse it
        p, u = self.getparser()
        while 1:
            if sock:
                response = sock.recv(1024)
            else:
                response = responsefile.read(1024)
            if not response:
                break
            if self.verbose:
                print "body:", repr(response)
            p.feed(response)
        responsefile.close()
        p.close()

        return u.close()


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
        cookie_request = urllib2.Request(request_url)
        
        self.send_request(h,handler,request_body)
        self.send_host(h,host)
        self.send_cookies(h,cookie_request) # ADDED. creates cookiejar if None.
        self.send_user_agent(h)
        self.send_content(h,request_body)


        try:
            # In Python <= 2.6, h is an HTTP object, which has a nice
            # "getreply" method.
            errcode, errmsg, headers = h.getreply()

        except AttributeError:
            # In other reasons we have an HTTPConnection, which has a
            # different interface
            resp = h.getresponse()
            errcode = resp.status
            errmsg = resp.reason
            headers = resp.msg


        # ADDED: parse headers and get cookies here
        # fake a response object that we can fill with the headers above

        class CookieResponse:
            def __init__(self,headers): 
                self.headers = headers
            def info(self): 
                return self.headers
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
            #return self._parse_response(h.getfile(), sock)
        except AttributeError:
            sock = None
            #
        return self._parse_response(resp)
        #return self._parse_response(h.getfile(), sock)

class SafeCookieTransport(xmlrpclib.SafeTransport,CookieTransport):
    '''SafeTransport subclass that supports cookies.'''
    scheme = 'https'
    request = CookieTransport.request
    



class BugzillaServer(object):
    def __init__(self, url, cookie_file):
        self.url = url
        self.cookie_file = cookie_file
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


        #username = "metrictool-group"
        #password = "passw0rd"

        debug('Logging in with username "%s"' % username)

        try:
            self.server.User.login({"login" : username, "password" : password})
        except xmlrpclib.Fault, err:
            print "A fault occurred:"
            print "Fault code: %d" % err.faultCode
            print "Fault string: %s" % err.faultString
        debug("logged in")
        self.cookie_jar.save;


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

    def show_bug(self, bug_id):
        print "Show Bug %s :" %bug_id
        return self.server.Bug.show_bug(bug_id)

    def add_comment(self, bug_id, comment, email_flag):
        print "Add comment to Bug"
        self.server.Bug.add_comment(bug_id, comment, email_flag)
        return True



def debug(s):
    """
    Prints debugging information if run with --debug
    """
    if DEBUG:
        print ">>> %s" % s
