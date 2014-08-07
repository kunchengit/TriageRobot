from Bugzilla_webservice import *
BUGZILLA_URL = 'https://bugzilla.eng.vmware.com/xmlrpc.cgi'
server = BugzillaServer(BUGZILLA_URL, '')
server.login('shinyeht','VMware123')
a = ["157_0_0"]

print a
server.add_fix_bys(1285687,a)
#test = server.show_bug(1285687)
#print test
