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

import re

def to_url(charts):
    """Generates a bugzilla query list from a boolean chart
   
    Each condition is represented by a tuple on the form
    (connective, field, operator, value); where conective must
    be None on the first condition of a chart and "AND" or "OR"
    in the others. See the Bugzilla manual or the fields and
    operators list definitions for valid fields and operators.

    Each chart is formed by a list of conditions. The charts 
    argument must be a list of charts.

    The returned value is a list of (key, value) tuples which can be
    be passed to urllib.urlencode
    """

    query = []
    chart_number = 0

    for chart in charts:
        and_number = 0
        or_number = 0

        for line in chart:
            (connective, field, operator, value) = line

            if connective == "AND":
                and_number = and_number + 1
                or_number = 0
                current = "%d-%d-%d" % (chart_number, and_number, or_number)

            elif connective == "OR":
                or_number = or_number + 1
                current = "%d-%d-%d" % (chart_number, and_number, or_number)

            else:
                if (and_number == 0) and (or_number == 0):
                    current = "%d-%d-%d" % (chart_number, and_number,
                        or_number)
                else:
                    raise ValueError("Invalid connective on boolean chart.")

            if field in fields:
                query.append(("field%s" % current, field))
            else:
                raise ValueError("Invalid field on boolean chart: %s" % field)
        
            if operator in operators:
                query.append(("type%s" % current, operator))
            else:
                raise ValueError("Invalid operator on boolean chart: %s" %
                    operator)

            query.append(("value%s" % current, value))

        chart_number = chart_number + 1

    return query

def str_to_chart(str):
    """Generate a chart from a string representation
    
    Parses a string and returns a chart which can be used on queries.

    Each condition should be represented by "(<field>, <operator>, <value>)";
    and joined together with "|" (or) or "&" (and). Charts should be
    separated by ":".
    """

    parser = re.compile("([|&])?\s*\((.*?),(.*?),(.*?)\)")
    connectives = { "|" : "OR", "&" : "AND", "" : None }
    charts = str.split(":")

    result = []

    for c in charts:
        chart = []

        lines = parser.findall(c)

        for l in lines:
            connective = connectives[l[0].strip()]
            field = l[1].strip()
            operator = l[2].strip()
            value = l[3].strip()

            chart.append((connective, field, operator, value))

        result.append(chart)

    return result

fields = []
fields.append("bug_id")
fields.append("short_desc")
fields.append("classification")
fields.append("product")
fields.append("version")
fields.append("rep_platform")
fields.append("bug_file_loc")
fields.append("op_sys")
fields.append("bug_status")
fields.append("status_whiteboard")
fields.append("keywords")
fields.append("resolution")
fields.append("bug_severity")
fields.append("priority")
fields.append("component")
fields.append("assigned_to")
fields.append("reporter")
fields.append("votes")
fields.append("qa_contact")
fields.append("cc")
fields.append("dependson")
fields.append("blocked")
fields.append("attachments.description")
fields.append("attachments.thedata")
fields.append("attachments.filename")
fields.append("attachments.mimetype")
fields.append("attachments.ispatch")
fields.append("attachments.isobsolete")
fields.append("attachments.isprivate")
fields.append("target_milestone")
fields.append("delta_ts")
fields.append("longdesc")
fields.append("alias")
fields.append("everconfirmed")
fields.append("reporter_accessible")
fields.append("cclist_accessible")
fields.append("bug_group")
fields.append("commenter")
fields.append("flagtypes.name")
fields.append("requestees.login_name")
fields.append("setters.login_name")
fields.append("content")
fields.append("days_elapsed")
fields.append("owner_idle_time")

operators = []
operators.append("equals")
operators.append("notequals")
operators.append("anyexact")
operators.append("substring")
operators.append("casesubstring")
operators.append("notsubstring")
operators.append("anywordssubstr")
operators.append("allwordssubstr")
operators.append("nowordssubstr")
operators.append("regexp")
operators.append("notregexp")
operators.append("lessthan")
operators.append("greatherthan")
operators.append("anyword")
operators.append("allwords")
operators.append("nowords")
operators.append("changedbefore")
operators.append("changedafter")
operators.append("changedfrom")
operators.append("changedto")
operators.append("changedby")
operators.append("matches")

# vim: tabstop=4 expandtab shiftwidth=4
