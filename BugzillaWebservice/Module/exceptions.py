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

class BZUtilsError(Exception):
    """Base class for exceptions in bzutils"""
    pass

class InvalidQueryError(BZUtilsError):
    """Invalid query exception"""
    pass

class BugListParseError(BZUtilsError):
    """Parse exception"""
    pass

class InvalidProductError(BZUtilsError):
    """Invalid product exception."""
    pass

class InvalidComponentError(BZUtilsError):
    """Invalid component exception."""
    pass

class InvalidVersionError(BZUtilsError):
    """Invalid version exception."""
    pass

# vim: tabstop=4 expandtab shiftwidth=4
