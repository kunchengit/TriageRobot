# bzutils -- Python module to interact with bugzilla servers.
# Copyright (C) 2007  Gustavo R. Montesino
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import exceptions

class Bug:
    """A single bugzilla bug report"""

    def __init__(self, id, server=None, product=None, component=None, 
        version=None, status=None, resolution=None, reporter=None, 
        assignee=None, summary=None, priority=None, severity=None, url=None):
        """Creates a bug instance"""

        # information about this bug -- can be set through the arguments
        self.set_id(id)
        self.set_server(server)
        self.set_product(product)
        self.set_component(component)
        self.set_version(version)
        self.set_status(status)
        self.set_resolution(resolution)
        self.set_reporter(reporter)
        self.set_assignee(assignee)
        self.set_summary(summary)
        self.set_priority(priority)
        self.set_severity(severity)
        self.set_url(url)

    def __str__(self):
        return """
Bug: %s -- %s
Product: %s
Component: %s
Version: %s
Status and Resolution: %s %s
Reporter: %s
Assigned To: %s
Priority and Severity: %s %s""" % (self.get_id().encode("utf-8"),
        self.get_summary().encode("utf-8"),
        self.get_product().encode("utf-8"),
        self.get_component().encode("utf-8"),
        self.get_version().encode("utf-8"),
        self.get_status().encode("utf-8"),
        self.get_resolution().encode("utf-8"),
        self.get_reporter().encode("utf-8"),
        self.get_assignee().encode("utf-8"),
        self.get_priority().encode("utf-8"),
        self.get_severity().encode("utf-8"))
    
    def get_id(self):
        return self.id
    
    def set_id(self, id):
        self.id = id

    def get_server(self):
        return self.server

    def set_server(self, server):
        #FIXME: validate it
        self.server = server
    
    def get_product(self):
        return self.product
    
    def set_product(self, product): 
        # Validate the product if it's != None and we have a server reference
        server = self.get_server()
        if product and server:
            if not product in server.get_products():
                raise exceptions.InvalidProductError("Invalid product: %s" % product)

        self.product = product
    
    def get_component(self):
        return self.component
    
    def set_component(self, component):
        #Validate the component if we have the needed data
        server = self.get_server()
        product = self.get_product()
        if server and product and component:
            if not component in server.get_components(product):
                raise exceptions.InvalidComponentError("Invalid component: %s" % component)

        self.component = component
    
    def get_version(self):
        return self.version

    def set_version(self, version):
        server = self.get_server()
        product = self.get_product()
        if server and product and version:
            valid_versions = server.get_versions(product)
            if version in valid_versions:
                self.version = version
            else:
                versions_abbr = [ver[0:5] for ver in valid_versions]
                if version in versions_abbr:
                    self.version = valid_versions[versions_abbr.index(version)]
                else:
                    raise exceptions.InvalidVersionError("Invalid version: %s" % version)
    
    def get_status(self):
        return self.status
    
    def set_status(self, status):
        self.status = status
    
    def get_resolution(self):
        return self.resolution
    
    def set_resolution(self, resolution):
        self.resolution = resolution
    
    def get_reporter(self):
        return self.reporter
    
    def set_reporter(self, reporter):
        self.reporter = reporter
    
    def get_assignee(self):
        return self.assignee
    
    def set_assignee(self, assignee):
        self.assignee = assignee
    
    def get_summary(self):
        return self.summary
    
    def set_summary(self, summary):
        self.summary = summary
    
    def get_priority(self):
        return self.priority
    
    def set_priority(self, priority):
        self.priority = priority
    
    def get_severity(self):
        return self.severity
    
    def set_severity(self, severity):
        self.severity = severity

    def get_url(self):
        return self.url

    def set_url(self, url):
        self.url = url

# vim: tabstop=4 expandtab shiftwidth=4
