
if __name__ == "__main__":
    from bugzilla import Bugzilla
    print "Start work"
    test = Bugzilla("https://bugzilla.eng.vmware.com/xmlrpc.cgi")
    print test.get("1284089")
