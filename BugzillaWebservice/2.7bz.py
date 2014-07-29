if __name__ == "__main__":
    from Bugzilla_webservice import *
    import xmlrpclib, urllib2, cookielib, os, getpass, sys
    import pprint
    from types import *
    from datetime import datetime, time
    from urlparse import urljoin, urlparse
    from cookielib import CookieJar
    from operator import itemgetter
    
    
    if 'USERPROFILE' in os.environ:
        homepath = os.path.join(os.environ["USERPROFILE"], "Local Settings",
                                "Application Data")
    elif 'HOME' in os.environ:
        homepath = os.environ["HOME"]
    else:
        homepath = ''

    cookie_file = os.path.join(homepath, ".bugzilla-cookies.txt")
    
    #bugzilla_url = options.bugzilla_url

    server = BugzillaServer('https://bugzilla.eng.vmware.com/xmlrpc.cgi', cookie_file)
    server.login()
    
    if len(sys.argv) < 1:
        print "You must specify a bug number"
        sys.exit(1)

    bug_id = sys.argv[1]

    #if (options.comment):
    #    server.add_comment(bug_id, options.comment)
    #    sys.exit(0)

    #if (options.withcolumns and options.nocolumns):
    #    print "--nocolumns and --withcolumns are mutually exclusive"
    #    sys.exit(1)
    
    bug = server.show_bug(bug_id)
    print bug
