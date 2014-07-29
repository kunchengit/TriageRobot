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

from cgi import CGI

class Bugzilla:
    """Backend-agnostic bugzilla interaction class

    This is the preferred way to communicate with bugzilla
    servers."""

    def __init__(self, baseurl):
        """Sets the url of the bugzilla server"""
        self.cgi = CGI(baseurl)

    def get_products(self):
        return self.cgi.get_products()

    def get_components(self, product):
        return self.cgi.get_components(product)

    def get_versions(self, product):
        return self.cgi.get_versions(product)

    def get(self, number):
        """Get a bug through its bug number/id"""

        charts = [[(None, "bug_id", "equals", number)]]
        return self.cgi.query_bchart(charts=charts)[0]
    
    def query(self, charts=None, str=None):
        """Query the bugzilla server using boolean charts

        Returns a list of bugs which match the query.

        The chart can be passed as a chart list or as a
        string, see the descriptions on the modules cgi
        and bchart
        """
        return self.cgi.query_bchart(charts=charts, str=str)

# vim: tabstop=4 expandtab shiftwidth=4
