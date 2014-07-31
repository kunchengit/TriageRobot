#!/usr/bin/python

import sys
import time
import tempfile
import pickle
import logging
from os.path import exists, join
from collections import namedtuple, defaultdict, OrderedDict # Python 2.7

import MySQLdb
from BID_Record import *
from BAR_Rules import *

#mysql -u mts -p -P 3306 -D bugzilla -h bz3-db3.eng.vmware.com
BUGZILLA_LINK="https://bugzilla.eng.vmware.com"
BUGZILLA_DATABASE_HOST = "bz3-db3.eng.vmware.com"
BUGZILLA_DATABASE_PORT = 3306
BUGZILLA_DATABASE_USER ="mts"
BUGZILLA_DATABASE_PW="mts"
BUGZILLA_DATABASE_DATABASE="bugzilla"

LOCAL_DATABASE_HOST = "localhost"
#LOCAL_DATABASE_PORT
LOCAL_DATABASE_USER = "root"
LOCAL_DATABASE_PW = "vmware"
LOCAL_DATABASE_DATABASE = "TriageRobot"

VERBOSE_LEVEL_DEFAULT   = 0
VERBOSE_LEVEL_BUG_LINK  = 1 # link
VERBOSE_LEVEL_BUG       = 2 # fix by, etc
VERBOSE_LEVEL_COMMENT   = 3

#ShinYeh Global Variable which are kept for recording
Keep_connect = 0
Keep_record = 0
FMT_YMDHMS  = "%Y-%m-%d %H:%M:%S"
FMT_YMD     = "%Y-%m-%d"

gOption = {}
gLogger = None

# Table Schema
"""
    When someone edits the Master table,  he/she has to remember to edit the 
        0.gRecordScheme, bugs namedtuple
        1.Rawdata_to_BID_Record
        2.Set_Bugs
    in BAR.py and BID_Record.py
    Without the correct modifications, the retreving data from Bugzilla will not be saved into our own data structure
    Besides, the function 
        Connect_With_OurDB
    in BAR.py should be checked since the type of new column should be classified into string or int
    by Shinyeh 0702
"""
gRecordSchema = {
    # Master table
    "bugs"      : namedtuple("table_bugs", "bug_id, assigned_to, short_desc, product_id, category_id, component_id, bug_status, keywords, resolution, delta_ts, bug_severity, cf_public_severity, cf_attempted, cf_failed, cf_reported_by, cf_eta, priority"),
    # lookup tables
    "profiles"  : namedtuple("table_profiles", "userid, login_name, realname"),
    "fielddefs" : namedtuple("table_fielddefs", "name, id, description"),
    "bug_status": namedtuple("table_bug_status", "value, id"),
    "products"  : namedtuple("table_products", "id, name, description"),
    "categories": namedtuple("table_categories", "id, name, product_id, description"),
    "components": namedtuple("table_components", "id, name, category_id, description"),
    "versions"  : namedtuple("table_versions", "id, name, description, product_id"),
    "phases"  : namedtuple("table_phases", "id, name, description, version_id"),
    # Bug detail tables
    "needinfo"      : namedtuple("table_needinfo", "bug_id, who"),
    "bug_fix_by_map": namedtuple("table_bug_fix_by_map", "bug_id, product_id, version_id, phase_id, id"),
    "bug_case_map"  : namedtuple("table_bug_case_map", "bug_id, case_id"),
    "longdescs"     : namedtuple("table_longdescs", "comment_id, bug_id, bug_when, who, thetext"),
    # composed bug record view.
    "bug_record"    : namedtuple("bug_record", "bugs, needinfo, fix_by, cases, comments"),
}

class BugzillaDB(object):
    def __init__(self, host=BUGZILLA_DATABASE_HOST, port=BUGZILLA_DATABASE_PORT, user=BUGZILLA_DATABASE_USER, passwd=BUGZILLA_DATABASE_PW, db=BUGZILLA_DATABASE_DATABASE):
        self.host, self.port, self.user, self.passwd, self.db = host, port, user, passwd, db

        self.conn = None
        self.db_index = {} # cache for lookup tables

    def __enter__(self):
        global Keep_connect # for keeping connection between MySQLdb and python alive
        global Keep_record
        try:
            if Keep_connect == 0:#Shinyeh In order to facilitate the query process
                self.conn = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.passwd, db=self.db)
                Keep_connect = self.conn

                #cache lookup tables, index
                lookup_tables = []
                """
                ShinYeh:All the name id version are retrieved from this function, and these information will be kept in lookup_tables and Keep_record
                sql:
                SELECT userid,login_name,realname FROM profiles
                SELECT name,id,description FROM fielddefs
                SELECT value,id FROM bug_status
                SELECT id,name,description FROM products
                SELECT id,name,product_id,description FROM categories
                SELECT id,name,category_id,description FROM components
                SELECT id,name,description,product_id FROM versions
                """
                for table_name in ("profiles", "fielddefs", "bug_status", "products", "categories", "components", "versions", "phases"):
                    sql = "SELECT {} FROM {}".format(",".join(gRecordSchema[table_name]._fields), table_name)
                    #print gRecordSchema[table_name]._fields
                    #print sql
                    
                    lookup_tables.append((table_name, gRecordSchema[table_name], join(tempfile.gettempdir(), "bz_{}.p".format(table_name)), sql))

                for table_name, schema, cache_file, sql in lookup_tables:
                    if exists(cache_file):
                        recordset = pickle.load(open(cache_file, "rb"))
                    else:
                        cursor = self.conn.cursor()
                        cursor.execute(sql)
                        recordset = cursor.fetchall()
                        
                        cursor.close()
                        pickle.dump(recordset, open(cache_file, "wb"))

                    recordset = map(schema._make, recordset)
                    
                    self.db_index[table_name] = dict(zip([record[0] for record in recordset], recordset))
                # index login_name on table profiles
                self.db_index["profiles_login_name"] = {}
                for userid in self.db_index["profiles"]:
                    record = self.db_index["profiles"][userid]
                    
                    #print self.db_index["profiles"][userid]
                    
                    self.db_index["profiles_login_name"][record.login_name] = record

                for table_name in self.db_index:
                    gLogger.debug("=" * 80)
                    title = "TABLE {}:".format(table_name)
                    gLogger.debug(title)
                    gLogger.debug("-" * len(title))
                    for k, v in self.db_index[table_name].items():
                        gLogger.debug("{} => {}".format(k, v))
                Keep_record = self.db_index #keep record
            else:#if the self.conn is already registered, the program just use the old database
                self.conn = Keep_connect
                self.db_index = Keep_record
            
            
            """
            Register for product Information
            Shinyeh 0701
            """
            self.product_id = []
            for okey in gOption.get("product"):
                for key in self.db_index["products"]:
                    if self.db_index["products"][key].name == okey:
                        self.product_id.append(str(key))
                        break;
                else:
                    self.product_id.append("bugs.product_id")
            return self
        except MySQLdb.Error, e:
            gLogger.error("Error %d: %s" % (e.args[0], e.args[1]))
            sys.exit (1)

    def __exit__(self, type, value, traceback):
        if not self.conn:
            self.conn.close()

    def _run_report_test(self):
        cursor = self.conn.cursor()

        sql = "SELECT VERSION()"
        cursor.execute(sql)
        record = cursor.fetchone()
        gLogger.debug("server version: %s" % record[0])

        cursor.close()

    def _fetch_bugs(self, sql, do_get_comments=True):
        r = {
            "bugs"          : {},
            "needinfo"      : defaultdict(list),
            "bug_fix_by_map": defaultdict(list),
            "bug_case_map"  : defaultdict(list),
            "longdescs"     : defaultdict(list),
        }
        #do_get_comments=False
        cursor = self.conn.cursor()
        # bugs table
        gLogger.debug(sql)
        cursor.execute(sql)
        bugs = r["bugs"]
        while True:
            record = cursor.fetchone()
            if not record: break
            record = gRecordSchema["bugs"]._make(record)
            
            #print record
            
            gLogger.debug(record)
            bugs[record.bug_id] = record

        bug_ids = ",".join([str(bug_id) for bug_id in bugs])
        if bug_ids:
            # more details: needinfo, sr, fix_by, comments
            for table_name in ("needinfo", "bug_fix_by_map", "bug_case_map", "longdescs"):
                schema = gRecordSchema[table_name]
                if table_name == "longdescs":
                    #In order to not get full details Edited by ShinYeh 0701
                    if gOption.get("verbose") < VERBOSE_LEVEL_COMMENT or not do_get_comments:
                    #if gOption.get("verbose") < VERBOSE_LEVEL_COMMENT:
                        continue
                    
                    try:#to match all the possible name
                        assigned_name_to = ",".join([str(self.db_index["profiles_login_name"][guid].userid) for guid in gOption.get("assigned_rn")])
                    except:
                        assigned_name_to = "longdescs.who"
                        
                    sql = """SELECT {} FROM {}
                             WHERE bug_id IN ({})
                             """.format(
                            ",".join(schema._fields),
                            table_name,
                            bug_ids,
                            assigned_name_to)
                else:
                    sql = "SELECT {} FROM {} WHERE bug_id IN ({})".format(
                        ",".join(schema._fields),
                        table_name,
                        bug_ids,)
                gLogger.debug(sql)
                cursor.execute(sql)
                while True:
                    record = cursor.fetchone()
                    if not record: break
                    record = gRecordSchema[table_name]._make(record)
                    gLogger.debug(record)
                    r[table_name][record.bug_id].append(record)

        cursor.close()

        return r

    def format_bug(self, bug_record):
        gLogger.debug(bug_record)

        # email subject format
        bug = bug_record.bugs
        r = """[Bug {}: {}: {}] {} {}
{}/show_bug.cgi?id={}
""".format(
                bug.bug_id,
                self.db_index["categories"][bug.category_id].name,
                self.db_index["components"][bug.component_id].name,
                "[SR]" if bug_record.cases else "",
                bug.short_desc,
                BUGZILLA_LINK,
                bug.bug_id,)

        if gOption.get("verbose") <= VERBOSE_LEVEL_BUG_LINK:
            return r

        for fix_by in bug_record.fix_by:
            product_id, version_id = fix_by.product_id, fix_by.version_id
            if version_id: # 0 => No "Fix By"
                r += " - {:<16}: {} {}\n".format(
                        "Fix By",
                        self.db_index["products"][product_id].name,
                        self.db_index["versions"][version_id].name,)

        r  += " - {:<16}: {}: {}\n".format(
              "Assigned to",
              self.db_index["profiles"][bug.assigned_to].login_name,
              self.db_index["profiles"][bug.assigned_to].realname,)

        if bug.bug_status in ("resolved", "closed"):
            r += " - {:<16}: {}, Resolution: {}\n".format("Status", bug.bug_status, bug.resolution)
        else:
            r += " - {:<16}: {}\n".format("Status", bug.bug_status)

        if bug_record.needinfo:
            r += " - {:<16}: {}\n".format(
                    "Needinfo",
                    "; ".join(["{}: {}".format(
                                               self.db_index["profiles"][record.who].login_name,
                                               self.db_index["profiles"][record.who].realname,)
                               for record in bug_record.needinfo
                               if record.who in self.db_index["profiles"]]))

        if gOption.get("verbose") >= VERBOSE_LEVEL_COMMENT and bug_record.comments:
            r += " - {:<16}: => \n".format("Comments")
            r += "\n".join(["{} | {}:\n{}\n".format(record.bug_when,
                                                 self.db_index["profiles"][record.who].realname,
                                                 record.thetext)
                            for record in bug_record.comments])

        return r

    def set_query_params(self, people, date_begin, date_end, product_rn):
        self.people, self.date_begin, self.date_end, self.product_rn= people, date_begin, date_end, product_rn

    """
    General Modification for each report sql query by ShinYeh 0630
    The rule of product_id has been implemented into the orginal sql query to facilitate the query process
    i.e., bygs.product_id = {} % self.product_id
    
    AND bugs.delta_ts BETWEEN '{}' AND '{}'
    AND bugs.product_id IN ({})
    """
    
    def run_report_incoming(self):
        """ Bugs Incoming: (incoming)
        *) Bugs have updates and newly assigned to <people>
        *) Bugs newly created and assigned to <people> directly -- TODO
        """
        try:#to match all the possible name
            assigned_to_name = ",".join(map(str, [self.db_index["profiles_login_name"][p].userid for p in self.people]))
        except:
            assigned_to_name = 'bugs.assigned_to'

        sql = """SELECT {} FROM bugs, bugs_activity
                 WHERE bugs.bug_id = bugs_activity.bug_id
                       AND (bugs_activity.fieldid = {}
                            AND bugs_activity.added IN ({})
                            AND bugs_activity.bug_when BETWEEN '{}' AND '{}') 
                       AND bugs.product_id IN ({})
                       AND bugs.assigned_to IN ({})
                       AND bugs.bug_status IN ({})""".format(
                ",".join(["bugs.{}".format(field) for field in gRecordSchema["bugs"]._fields]),
                self.db_index["fielddefs"]["assigned_to"].id,
                ",".join(["'{}'".format(p) for p in self.people]),
                self.date_begin,
                self.date_end,
                ",".join(["{}".format(p) for p in self.product_id]),
                assigned_to_name,
                ",".join(["'{}'".format(s) for s in ("new", "reopened", "assigned", "needinfo")]))

        return self._fetch_bugs(sql)

    def run_report_outgoing(self):
        """ Bugs Outgoing: (outgoing)
        *) Bugs resolved by <people>
        """
        try:#to match all the possible name
            assigned_to_name = ",".join(map(str, [self.db_index["profiles_login_name"][p].userid for p in self.people]))
        except:
            assigned_to_name = 'bugs.assigned_to'
        
        sql = """SELECT {} FROM bugs, bugs_activity
                 WHERE
                       (bugs.assigned_to IN ({})
                        AND bugs.bug_status IN ({}))
                       AND bugs.bug_id = bugs_activity.bug_id
                       AND (bugs_activity.fieldid = {}
                            AND bugs_activity.added IN ({})
                            AND bugs_activity.bug_when BETWEEN '{}' AND '{}') 
                       AND bugs.product_id IN ({})""".format(
                ",".join(["bugs.{}".format(field) for field in gRecordSchema["bugs"]._fields]),
                assigned_to_name,
                ",".join(["'{}'".format(s) for s in ("resolved", "closed")]),
                self.db_index["fielddefs"]["bug_status"].id,
                ",".join(["'{}'".format(s) for s in ("resolved", )]),
                self.date_begin,
                self.date_end,
                ",".join(["{}".format(p) for p in self.product_id]))

        return self._fetch_bugs(sql)

    def run_report_commented(self):
        """ Bugs have update activities: (commented)
        *) Bugs commented by <people>
        
        Modified by Shinyeh
        bugs.product_id and bugs.assigned_to
        """
        try:#to match all the possible name
            assigned_to_name = ",".join(map(str, [self.db_index["profiles_login_name"][p].userid for p in self.people]))
        except:
            assigned_to_name = 'bugs.assigned_to'
                    
        sql = """SELECT DISTINCT {} FROM bugs, longdescs, products
                 WHERE bugs.bug_id = longdescs.bug_id
                       AND longdescs.who IN ({})
                       AND longdescs.bug_when BETWEEN '{}' AND '{}'
                       AND bugs.product_id IN ({})
                       AND bugs.assigned_to IN ({})
                       AND bugs.bug_status IN ({})""".format(
                ",".join(["bugs.{}".format(field) for field in gRecordSchema["bugs"]._fields]),
                assigned_to_name,
                self.date_begin,
                self.date_end, 
                ",".join(["{}".format(p) for p in self.product_id]),
                assigned_to_name, 
                ",".join(["'{}'".format(s) for s in ("new", "reopened", "assigned", "needinfo")]))
        return self._fetch_bugs(sql, do_get_comments=True)

    def run_report_assigned_to(self):
        """ Bug Queue: (backlog)
        *) Bugs assigned to <people> currently not resolved or closed.        
        """
        try:#to match all the possible name
            assigned_to_name = ",".join(map(str, [self.db_index["profiles_login_name"][p].userid for p in self.people]))
        except:
            assigned_to_name = 'bugs.assigned_to'
        sql = """SELECT {} FROM bugs
                 WHERE bugs.assigned_to IN ({}) AND bugs.bug_status IN ({})
                 AND bugs.delta_ts BETWEEN '{}' AND '{}'
                 AND bugs.product_id IN ({})""".format(
                ",".join(["bugs.{}".format(field) for field in gRecordSchema["bugs"]._fields]),
                assigned_to_name,
                ",".join(["'{}'".format(s) for s in ("new", "reopened", "assigned", "needinfo")]),
                self.date_begin,
                self.date_end,
                ",".join(["{}".format(p) for p in self.product_id]))
        return self._fetch_bugs(sql)

    def run_report_guru_duty(self):
        """ Bugs touched as Guru Duty: (guru)
        *) Provide info for needinfo, or needinfo somebody (on bugs that is not aissgned to <people>)
        *) Assigned bug to somebody else
        """
        try:#to match all the possible name
            assigned_to_name = ",".join(map(str, [self.db_index["profiles_login_name"][p].userid for p in self.people]))
        except:
            assigned_to_name = 'bugs.assigned_to'
        
        sql = """SELECT DISTINCT {} FROM bugs, bugs_activity
                 WHERE bugs.bug_id = bugs_activity.bug_id
                       AND bugs.assigned_to NOT IN ({})
                       AND (bugs_activity.who IN ({})
                            AND bugs_activity.fieldid IN ({})
                            AND bugs_activity.bug_when BETWEEN '{}' AND '{}') 
                       AND bugs.product_id IN ({})
                       AND bugs.bug_status IN ({})""".format(
                ",".join(["bugs.{}".format(field) for field in gRecordSchema["bugs"]._fields]),
                assigned_to_name,
                assigned_to_name,
                ",".join(map(str, (self.db_index["fielddefs"]["assigned_to"].id, self.db_index["fielddefs"]["needinfo"].id))),
                self.date_begin,
                self.date_end, 
                ",".join(["{}".format(p) for p in self.product_id]),
                ",".join(["'{}'".format(s) for s in ("new", "reopened", "assigned", "needinfo")]))
        return self._fetch_bugs(sql)


REPORTS = [ "incoming", "outgoing", "commented", "backlog", "guru" ]

def run_report_for(*argv):
    people, date_begin, date_end , product_rn= argv
    with BugzillaDB() as bzdb:
        #bzdb._run_report_test()
        if gOption.get("individual"):
            groups = [[p] for p in people]
        else:
            groups = [people]

        for people in groups:
        
            title = "Progress:\t {} ({} ~ {}) {}".format(
                    people, gOption.get("D_begin"), gOption.get("D_end"), gOption.get("product"))
            gLogger.info(title)
            """
            title = "Bugzilla Activity Report: {} ({} ~ {})".format(
                    people, gOption.get("D_begin"), gOption.get("D_end"))
            gLogger.info("\n")
            gLogger.info("+" * len(title))
            gLogger.info(title)
            gLogger.info("+" * len(title))
            """
            bzdb.set_query_params(people, date_begin, date_end, product_rn)
            """
            Shinyeh, I removed Outgoing since I found out that the tool did not care about the closed event
            reports = OrderedDict([#report_index -> report_func
                ("incoming" , bzdb.run_report_incoming),
                ("outgoing" , bzdb.run_report_outgoing), 
                ("commented", bzdb.run_report_commented),
                ("backlog"  , bzdb.run_report_assigned_to),
                ("guru"     , bzdb.run_report_guru_duty),
            ])
            """
            reports = OrderedDict([#report_index -> report_func
                ("incoming" , bzdb.run_report_incoming),
                #("outgoing" , bzdb.run_report_outgoing), 
                ("commented", bzdb.run_report_commented),
                ("backlog"  , bzdb.run_report_assigned_to),
                #("guru"     , bzdb.run_report_guru_duty),
            ])
            
            """
            Edited by Shinyeh
            Transform the bugs report into a summation of reports
            """
            sum_bugs_report = {}
            for report_index, report_func in reports.items():
                if report_index in gOption.get("reports"):
                    gLogger.info("\n")
                    bugs_report = report_func()
                    #Edited by ShinYeh
                    #print bugs_report
                    sum_bugs_report[report_index] = bugs_report
                    #print sum_bugs_report[report_index]
                    #Edited by ShinYeh
                    report_title = "{:<12} Total: {}".format(report_index, len(bugs_report["bugs"]))
                    
                    gLogger.info(report_title)
                    gLogger.info("-" * len(report_title))
                    bug_list = "{}/buglist.cgi?bug_id={}".format(
                                BUGZILLA_LINK,
                                ",".join([str(bug_id) for bug_id in bugs_report["bugs"]]))
                    gLogger.info(bug_list)
                    #gLogger.info("~" * 80)
                    if gOption.get("verbose") > VERBOSE_LEVEL_DEFAULT:
                        # XXX: sort by fix_by, delta_ts
                        for bug_id in bugs_report["bugs"]:
                            bug_record = gRecordSchema["bug_record"]._make(
                                (bugs_report["bugs"][bug_id],
                                 bugs_report["needinfo"][bug_id],
                                 bugs_report["bug_fix_by_map"][bug_id],
                                 bugs_report["bug_case_map"][bug_id],
                                 bugs_report["longdescs"][bug_id]))
                            #gLogger.info(bzdb.format_bug(bug_record))
                    """ 
                    Edited by shinyeht 0625
                    """
                    
    return sum_bugs_report
    
def Match_and_Output(Rules, Query_result, check_resolved):
    """
    This function handles the rule match.
    All the rule classification is processed by this function with the interface of BAR_rules
    This function also generates the bugs list for terminal user.
    """
    if check_resolved == False:
        CHECK_REPORTS = [ "incoming",  "commented", "backlog"]
    else:
        CHECK_REPORTS = [ "incoming",  "outgoing", "commented", "backlog", "guru"]
    #REPORTS = [ "incoming", "outgoing", "commented", "backlog", "guru" ]
    CHECK_REPORTS = [ "incoming",  "commented", "backlog"]
    Total_Result={}
    Match_Map=[]
    for okey in Rules:
        Input={}
        Urgent={}
        Normal={}
        #Match_Map=[]
        gLogger.info("="*len(str(okey.data.values())))
        gLogger.info(okey.data.values())
        gLogger.info("="*len(str(okey.data.values())))
        for rkey in CHECK_REPORTS:
            base = Query_result[str(okey)][rkey]
            Loader = Rawdata_to_BID_Record(base, Keep_record)
            for key in Loader:
                Input[key] = Loader[key]
            for bug_id in Input.keys():
                if bug_id not in Match_Map:
                    Match_Map.append(bug_id)
                    Urgent_Test_Result = Urgent_Test(Input[bug_id], okey, Keep_connect)
                    if Urgent_Test_Result == "Urgent":
                        Urgent[bug_id] = Input[bug_id]
                    elif Urgent_Test_Result == "Normal":
                        Normal[bug_id] = Input[bug_id]
                    else:#Uncared Situation since the bug does not fit fix_by_map rule (option.p)
                        continue
                    Total_Result[bug_id] = Input[bug_id]
                    
                    #else:
                    #    print "pass"
        gLogger.info("Urgent")
        bug_list = "{}/buglist.cgi?bug_id={}".format(BUGZILLA_LINK,",".join([str(bug_id) for bug_id in Urgent.keys()]))
        gLogger.info(bug_list)
                
        gLogger.info("Normal")
        bug_list = "{}/buglist.cgi?bug_id={}".format(BUGZILLA_LINK,",".join([str(bug_id) for bug_id in Normal.keys()]))
        gLogger.info(bug_list)
             
    return Total_Result      
def Connect_With_OurDB(Total_Result, Rules=[], Update=False, Update_end=None):
    """
    This function handles our database.
    When the user transmis the results into this funciton with corrent format (the format which is generated by original program), this function will help user to update the bugs into the lcoal database
    """
    
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    cursor = conn.cursor()
    
    
    str_columns = ["assigned_rn", "short_desc","product_rn","category_rn","component_rn", "bug_status","keywords","resolution","delta_ts","bug_severity","cf_public_severity", "cf_reported_by", "cf_eta", "priority","highlighted_by"]
    fix_by_map = ["fix_by_product_rn", "fix_by_version_rn", "fix_by_phase_rn", "fix_by_product_id", "fix_by_version_id", "fix_by_phase_id", "fix_by_id"]
    comments = ["ld_id", "ld_when", "ld_who", "ld_text"]
    
    """
    Since the fix_by_map columns have list data structude, the sql of these lists has to process seperately
    """
    for key in Total_Result:
        temp_sql={}
        sdata = Total_Result[key].data
        for dickey in sdata.keys():
            """
            Start String Processing for matching the requirement of sql
            """
            if dickey in fix_by_map or dickey in comments:#Skip the bug_fix_by_map column
                continue
            elif dickey in str_columns:#Process String
                temp_sql[dickey] = "'"+str(sdata[dickey]).replace("\\","\\\\").replace("\'","\\\'")+"'"
                if not sdata[dickey]:
                    sdata[dickey] = '---'
                #print key, sdata[a], temp_sql[a]
            else:#Process Int or Float
                temp_sql[dickey] = str(sdata[dickey]).strip('[\']')
                if not temp_sql[dickey]:
                    temp_sql[dickey] = "0"
        if sdata["bug_status"] not in ["resolved", "closed"]:
            sql = """INSERT INTO bugs 
                    ({})
                    VALUES 
                    ({})
                    ON DUPLICATE KEY UPDATE
                    {}
                    """.format(
                    ','.join(temp_sql.keys()),
                    ','.join(temp_sql.values()),
                    ','.join('{}={}'.format(k,temp_sql[k]) for k in temp_sql)
                    )     # python variables
        else:
            sql = """DELETE FROM bugs where bug_id = {}
            """.format(sdata["bug_id"])
        
        cursor.execute(sql)
    """
    Process bug_fix_by_map
    In order to sort and avoid duplicate records, I implement md5 for each bug
    Some bugs will have multiple columns of bug_fix_by_map
    """
    for key in Total_Result:
        sdata = Total_Result[key].data
        for ikey in range(0,len(sdata["fix_by_product_id"])):
            temp_sql={}
            for dkey in fix_by_map:
                if isinstance(sdata[dkey][ikey], str):
                    temp = sdata[dkey][ikey].replace("\\","\\\\").replace("\'","\\\'") #replace / -> // and ' -> /'
                    temp_sql[dkey] = "'"+ temp +"'"
                    #temp_sql[dkey] = "'"+sdata[dkey][ikey]+"'"
                else:
                    temp_sql[dkey] = str(sdata[dkey][ikey])
            temp_sql["bug_id"] = str(sdata["bug_id"])
            if sdata["bug_status"] not in ["resolved", "closed"]:
                sql = """INSERT INTO bug_fix_by_map 
                        ({})
                        VALUES 
                        ({})
                        ON DUPLICATE KEY UPDATE
                        {}
                        """.format(
                        ','.join(temp_sql.keys()),
                        ','.join(temp_sql.values()),
                        ','.join('{}={}'.format(k,temp_sql[k]) for k in temp_sql)
                        )     # python variables
            else:
                sql = """DELETE FROM bug_fix_by_map where bug_id = {}
                """.format(sdata["bug_id"])
            cursor.execute(sql)
    """
    Process longdescs(comments)
    There is no critical duplicate problems in comments section since there is comment_id
    Most of the bugs have several comments.
    PS: The text part should be process independently since there are lots of strange characters in text
    """
    
    for key in Total_Result:
        sdata = Total_Result[key].data
        for ikey in range(0,len(sdata["ld_id"])):
            temp_sql={}
            for dkey in comments:
                if isinstance(sdata[dkey][ikey], str):
                    if dkey == 'ld_text':
                        temp = sdata[dkey][ikey].replace("\\","\\\\").replace("\'","\\\'") #replace / -> // and ' -> /'
                        temp_sql[dkey] = "'"+ temp +"'"
                    else:
                        temp_sql[dkey] = "'"+sdata[dkey][ikey]+"'"
                elif isinstance(sdata[dkey][ikey], datetime):
                    temp_sql[dkey] = "'"+str(sdata[dkey][ikey])+"'"
                else:
                    temp_sql[dkey] = str(sdata[dkey][ikey])
            temp_sql["bug_id"] = str(sdata["bug_id"])
            if sdata["bug_status"] not in ["resolved", "closed"]:
                sql = """INSERT INTO longdescs
                        ({})
                        VALUES 
                        ({})
                        ON DUPLICATE KEY UPDATE
                        {}
                        """.format(
                        ','.join(temp_sql.keys()),
                        ','.join(temp_sql.values()),
                        ','.join('{}={}'.format(k,temp_sql[k]) for k in temp_sql)
                        )     # python variables
            else:
                sql = """DELETE FROM longdescs where bug_id = {}
                """.format(sdata["bug_id"])
            cursor.execute(sql)
    
    
    """
    Update the rules into database for future query
    If the database found out that the rule is queried before, the php will query our own database directly.
    Otherwise, the php will ask the python to query the bugzilla database
    """
    for rkey in Rules:#each rule
        temp_sql={}
        temp_md5=""
        for dkey in rkey.data.keys():#Dictionary Key, each column (list structure) in rules
            if isinstance(rkey.data[dkey], list):
                temp_sql[dkey] = "'{}'".format(','.join(map(str,rkey.data[dkey])))
            else:
                temp_sql[dkey] = "'" + str(rkey.data[dkey]) + "'"
            if dkey not in "D_begin, D_end":
                temp_md5= temp_md5 + "{}".format(','.join(map(str,rkey.data[dkey])))
            #temp_md5 = "'" + k + "'" for k in rkey.data[dkey]
            #for lkey in range(0,len(rkey.data[dkey])):#List Key, each item in list
            #    temp_md5 = temp_md5 + str(rkey.data[dkey][lkey])
            #    if isinstance(rkey.data[dkey][lkey], str):
            #        temp_sql[dkey] = temp_sql[dkey] + "'" + rkey.data[dkey][lkey] + "'"
            #    else:
            #        temp_sql[dkey] = str(rkey.data[dkey][lkey])
        temp_sql["md5"] = "'" + hashlib.md5(temp_md5).hexdigest() + "'"
        sql = """INSERT INTO rules
        ({})
        VALUES
        ({})
        ON DUPLICATE KEY UPDATE
        {}
        """.format(
        ','.join(temp_sql.keys()),
        ','.join(temp_sql.values()),
        ','.join('{}={}'.format(k,temp_sql[k]) for k in temp_sql)
        )
        cursor.execute(sql)
    """
    If the args.update is triggered, the script should update the system
    """    
        
    if Update:
        sql = """INSERT INTO update_information
        (update_time)
        VALUES
        ('{}')
        """.format(Update_end)
        cursor.execute(sql)
    cursor.close()
    conn.commit()
    conn.close()
def Update_Information():
    """
    This function copies all the profile, products and version into local database.
    This function costs lots of time.
    If the programmer wants to update the server without this function, it can parse --wo_update_information when triggered this BAR.py
    Since the datatype is copied from remote bugzilla database
    This part of the script is hard to format it into OOP
    """
    print 'Update...profiles...',
    sys.stdout.flush()
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    cursor = conn.cursor()
    for key in Keep_record["profiles"]:
        data = Keep_record["profiles"][key]
        sql = """INSERT INTO profiles
        (userid,login_name,realname)
        VALUES
        ({},{},{})
        ON DUPLICATE KEY UPDATE
        userid={},login_name={},realname={}
        """.format(data[0], "'"+data[1]+"'", "'"+data[2].replace("'", "\\'")+"'", data[0], "'"+data[1]+"'", "'"+data[2].replace("'", "\\'")+"'"
        )
        cursor.execute(sql)
    #"versions"  : namedtuple("table_versions", "id, name, description, product_id"),
    print "versions...",
    for key in Keep_record["versions"]:
        data = Keep_record["versions"][key]
        sql = """INSERT INTO versions
        (id,name,product_id)
        VALUES
        ({},{},{})
        ON DUPLICATE KEY UPDATE
        id={},name={},product_id={}
        """.format(data[0], "'"+data[1]+"'", data[3], data[0], "'"+data[1]+"'", data[3]
        )
        cursor.execute(sql)
    #"phases"  : namedtuple("table_phases", "id, name, description, version_id"),   
    print "phases...",
    for key in Keep_record["phases"]:
        data = Keep_record["phases"][key]
        sql = """INSERT INTO phases
        (id,name,version_id)
        VALUES
        ({},{},{})
        ON DUPLICATE KEY UPDATE
        id={},name={},version_id={}
        """.format(data[0], "'"+data[1]+"'", data[3], data[0], "'"+data[1]+"'", data[3]
        )
        cursor.execute(sql)    
    #"products"  : namedtuple("table_products", "id, name, description"),
    print "products..."
    for key in Keep_record["products"]:
        data = Keep_record["products"][key]
        sql = """INSERT INTO products
        (id,name)
        VALUES
        ({},{})
        ON DUPLICATE KEY UPDATE
        id={},name={}
        """.format(data[0], "'"+data[1]+"'", data[0], "'"+data[1]+"'"
        )
        cursor.execute(sql)
    print "Finish Update"
    cursor.close()
    conn.commit()
    conn.close()
    
def Periodically_Update(Get_ID = True):
    """
    Query Information and connect with our db
    This function retrieve all the bug_id from our database
    The function compares the latest update time and generates the bug_id list
    """
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    cursor = conn.cursor()
    Bug_id_Result=[]
    
    """
    When we set Get_ID into false, we would not retrieve the id data for improving efficiency
    """
    if Get_ID:
        sql = """SELECT bug_id from bugs"""
        cursor.execute(sql)
        while True:
            record = cursor.fetchone()
            if not record:
                break
            Bug_id_Result.append(record[0])
    #Total_Bug_id = ",".join(map(str, Result))
    
    sql = """SELECT update_time from update_information 
    where update_time in (select max(update_time) from update_information)
    """
    cursor.execute(sql)
    Result = cursor.fetchone()
    cursor.close()
    conn.close()
    """
    The time should be changed to asia time, since the modified time on Bugzilla is PST time
    Therefore, I sub a day of GMT+8
    """
    if Result:
        return [(Result[0]-timedelta(hours=15)).strftime(FMT_YMDHMS), Bug_id_Result]
    else:
        now = datetime.now()
        return [datetime(now.year, 1,1).strftime(FMT_YMDHMS), Bug_id_Result]
    
def Update_With_OriginalID(Previous_Result, Update_begin, Update_end, Update_bug_id):
    """
    This function updates the bugs into local database.
    This function will only be triggered when the user type --update
    """
    with BugzillaDB() as bzdb:
        
        sum_bugs_report = {}
        if not Update_bug_id:
                return False
        sql = """SELECT {} FROM bugs
                 WHERE
                 bugs.delta_ts BETWEEN '{}' AND '{}'
                 AND bugs.bug_id IN ({})""".format(
                ",".join(["bugs.{}".format(field) for field in gRecordSchema["bugs"]._fields]),
                Update_begin,
                Update_end,
                ",".join(map(str, Update_bug_id)))
        bugs_report = bzdb._fetch_bugs(sql)
        #Edited by ShinYeh
        sum_bugs_report['backlog'] = bugs_report
    #REPORTS = [ "incoming", "outgoing", "commented", "backlog", "guru" ]
    #CHECK_REPORTS = [ "incoming",  "commented", "backlog"]
    
    Total_Result={}

    
    Input={}
    base = sum_bugs_report["backlog"]
    Loader = Rawdata_to_BID_Record(base, Keep_record)
    
    for key in Loader:
        if key in Previous_Result.keys():
            continue
        Input[key] = Loader[key]
    
    for bug_id in Input.keys():
        Urgent_Test_Result = Urgent_Test(Input[bug_id], None, Keep_connect)
        if Urgent_Test_Result not in ["Urgent", "Normal"]:#Uncared Situation since the bug does not fit fix_b_map rule (option.p)
            continue
        Total_Result[bug_id] = Input[bug_id]
    return Total_Result

def Update_Milestone():
    import urllib2
    import ast
    import time
    #start = datetime.now()
    """
    Retrieve the timeline message from Static php
    """
    MILESTONE_URL = "http://mt-db2.eng.vmware.com/lib/Examples.php"
    #MILESTONE_URL = "http://10.117.8.249/"
    
    """
    Replace the null string into "null" for matching sql
    """
    temp_read = urllib2.urlopen(MILESTONE_URL).read() . replace('null', '"null"')
    milestone_results = ast.literal_eval(temp_read)
    
    
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    cursor = conn.cursor()
    
    def format_sql(input_string):
        if isinstance(input_string, str):
            return "'" + input_string + "'"
        elif isinstance(input_string, int):
            return input_string
        else:
            print "Check", input_string
            return input_string
    for entry in milestone_results:
        """
        the null key and value have to be removed
        """
        for key in entry.keys():
            if entry[key] =='null':
                del entry[key]
        sql = """INSERT INTO milestone
        ({})
        VALUES
        ({})
        ON DUPLICATE KEY UPDATE
        {}
        """.format(
        ','.join(entry.keys()),
        ','.join(map(str, (format_sql(k) for k in entry.values()))),
        ','.join('{}={}'.format(k,format_sql(entry[k])) for k in entry)
        )
        cursor.execute(sql)
    cursor.close()
    conn.commit()
    conn.close()
    #end = datetime.now()
    #print end-start
    return True

if __name__ == "__main__":
    import time
    import string
    import cgitb
    import cgi
    import argparse
    import re
    import hashlib
    from datetime import datetime, timedelta

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    gLogger = logging.getLogger()
    stdoutStreamHandler = logging.StreamHandler(stream=sys.stdout)
    # gLogger.addHandler(stdoutStreamHandler)
    gLogger.handlers = [stdoutStreamHandler]

    """
    if "cgi" in sys.argv[0]: #bugzilla-activity-report.py
        cgitb.enable()
        print("Content-Type: text/plain\r\n")
    fs = cgi.FieldStorage()
    for o in fs:
        sys.argv.append("--{}".format(o))
        sys.argv.append(fs[o].value)

    FMT_YMDHMS  = "%Y-%m-%d %H:%M:%S"
    FMT_YMD     = "%Y-%m-%d"

    epilog = "\n".join([getattr(BugzillaDB, e).__doc__ for e in dir(BugzillaDB) if e.startswith("run_report_")])

    parser = argparse.ArgumentParser(description="Bugzilla Activity Report", epilog=epilog,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--people', metavar='guid', nargs='+', default=["cpd-platform"], help='e.g. hfu,cpd-platform. Run report for these IDs.')
    parser.add_argument('--individual', action="store_true", default=False, help="Generate a report for each individual ID.")

    now = datetime.now()
    date_end = datetime(now.year, now.month, now.day)
    if date_end.weekday() > 2: # 2 -> Wed.
        # next Sun
        date_end += timedelta(days=(6-date_end.weekday()))
    else:
        # last Sun
        date_end -= timedelta(days=(date_end.weekday()+1))
    date_begin = date_end - timedelta(days=14)
    date_begin_str = date_begin.strftime(FMT_YMD)
    date_end_str = date_end.strftime(FMT_YMD)
    parser.add_argument('--date-begin', default=date_begin_str,
                        help="e.g. {}. Report period, begin time. default Monday of 2 weeks ago.".format(date_begin_str))
    parser.add_argument('--date-end', default=date_end_str,
                        help="e.g. {}. Report period, end time. default nearest Saturday.".format(date_end_str))

    parser.add_argument('--reports', metavar='report', nargs="+", default=["backlog"],
                        help="report in [{}]".format(",".join(REPORTS)))
    parser.add_argument('--verbose', type=int, default=0,
                        help="default 0. ({}: show summary. {}: show bug detail. {}: show comment detail.)".format(
                             VERBOSE_LEVEL_DEFAULT, VERBOSE_LEVEL_BUG_LINK, VERBOSE_LEVEL_BUG, VERBOSE_LEVEL_COMMENT))

    args = parser.parse_args()
    """
    #Shinyeh Edited by open option.p
    
    #f=open("option.p", "r")
    
    parser = argparse.ArgumentParser(description="Bugzilla Activity Report",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    
    parser.add_argument('--update', default=False, action='store_const', const=True, help='update per 15 minutes')
    parser.add_argument('--wo_update_information', default=True, action='store_const', const=False, help='update profile, version, products')
    parser.add_argument('--option', nargs=1, default="option.p", help='Enter the path of option.p')
    parser.add_argument('--milestone', default=False, action='store_const', const=True, help='Update Milestone to local data base. This process costs about 150 seconds and is unable to run with other job because of the time.')
    parser.add_argument('--ID', default=False, metavar='N', type=int, nargs='+', help='Do ID Update! This mode can not interact with other normal functions')
    
    args = parser.parse_args()
    
    """
    Run Update per 15 minutes
    """
    
    if args.ID:
        """
        The major function of this part is Check_ID
        """
        def format_sql(input_string, comments_flag=False):
            from datetime import date
            if isinstance(input_string, str):
                return "'" + input_string + "'"
            elif isinstance(input_string, int):
                return input_string
            elif isinstance(input_string, datetime):
                return "'" + str(input_string) + "'"
            elif isinstance(input_string, date):
                return "'" + str(input_string) + "'"
            else:
                return input_string
        def Check_ID(args):
            """
            This function only updates specific bug_id.
            Careful!!!!!
            This function does not update long_desc and bug_fix_by_map
            0728 Shinyeh
            """
            sql = """SELECT {} FROM bugs
                     WHERE bug_id in ({})""".format(
                    ",".join(["bugs.{}".format(field) for field in gRecordSchema["bugs"]._fields]),
                    ",".join(map(str,args.ID)))
            
            bzdb_conn = MySQLdb.connect(host=BUGZILLA_DATABASE_HOST, port=BUGZILLA_DATABASE_PORT, user=BUGZILLA_DATABASE_USER, passwd=BUGZILLA_DATABASE_PW, db=BUGZILLA_DATABASE_DATABASE)
            bzdb_cursor = bzdb_conn.cursor()
            
            local_conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
            local_cursor = local_conn.cursor()
            
            
            bzdb_cursor.execute(sql)
            columns = [column[0] for column in bzdb_cursor.description]
            Bugs_Results = []
            for row in bzdb_cursor.fetchall():
                Bugs_Results.append(dict(zip(columns, row)))
            
            for entry in Bugs_Results:
                for key in entry.keys():
                    if entry[key] == None:
                        del entry[key]
            
            
            for entry in Bugs_Results:
                if entry["bug_status"] not in ["resolved", "closed"]:
                    sql = """INSERT INTO bugs
                    ({})
                    VALUES
                    ({})
                    ON DUPLICATE KEY UPDATE
                    {}
                    """.format(
                    ','.join(entry.keys()),
                    ','.join(map(str,(format_sql(k) for k in entry.values()))),
                    ','.join('{}={}'.format(k,format_sql(entry[k])) for k in entry)
                    )
                else:
                    sql = """DELETE FROM bugs where bug_id = {}
                    """.format(entry["bug_id"])
                local_cursor.execute(sql)
                
            """
            Comments Update
            """
            sql = """SELECT {} FROM longdescs
                     WHERE bug_id in ({})""".format(
                    ",".join(["longdescs.{}".format(field) for field in gRecordSchema["longdescs"]._fields]),
                    ",".join(map(str,args.ID)))    
            
            bzdb_cursor.execute(sql)
            columns = [column[0] for column in bzdb_cursor.description]
            Comments_Results = []
            for row in bzdb_cursor.fetchall():
                Comments_Results.append(dict(zip(columns, row)))
            """
            Change dictionary name
            comment_id -> ld_id
            bug_id -> bug_id
            who -> ld_who
            bug_when -> ld_when
            thetext -> ld_text
            """
            for entry in Comments_Results:
                entry["ld_id"] = entry.pop("comment_id")
                #entry["bug_id"] = entry.pop("bug_id")
                entry["ld_who"] = entry.pop("who")
                entry["ld_when"] = entry.pop("bug_when")
                entry["ld_text"] = entry.pop("thetext")
                entry["ld_text"] = entry["ld_text"].replace("\\","\\\\").replace("\'","\\\'")
            
            for entry in Comments_Results:
                for key in entry.keys():
                    if entry[key] == None:
                        del entry[key]
            
            for entry in Comments_Results:
                sql = """INSERT INTO longdescs
                ({})
                VALUES
                ({})
                ON DUPLICATE KEY UPDATE
                {}
                """.format(
                ','.join(entry.keys()),
                ','.join(map(str,(format_sql(k) for k in entry.values()))),
                ','.join('{}={}'.format(k,format_sql(entry[k])) for k in entry)
                )
                local_cursor.execute(sql)
                
            """
            Update Bug_fix_by table
            """
            sql = """SELECT {} FROM bug_fix_by_map
                     WHERE bug_id in ({})""".format(
                    ",".join(["bug_fix_by_map.{}".format(field) for field in gRecordSchema["bug_fix_by_map"]._fields]),
                    ",".join(map(str,args.ID)))    
            
            
            
            bzdb_cursor.execute(sql)
            columns = [column[0] for column in bzdb_cursor.description]
            Fix_by_Results = []
            for row in bzdb_cursor.fetchall():
                Fix_by_Results.append(dict(zip(columns, row)))

            """
            Change dictionary name
            id -> fix_by_id
            bug_id -> bug_id
            product_id -> fix_by_product_id
            version_id -> fix_by_version_id
            phase_id -> fix_by_phase_id
            """
            for entry in Fix_by_Results:
                entry["fix_by_id"] = entry.pop("id")
                #entry["bug_id"] = entry.pop("bug_id")
                entry["fix_by_product_id"] = entry.pop("product_id")
                entry["fix_by_version_id"] = entry.pop("version_id")
                entry["fix_by_phase_id"] = entry.pop("phase_id")
                if entry["fix_by_product_id"] == 0:
                    entry["fix_by_product_rn"] = "Unknown"
                else:
                    sql = """select name from products where id = {}""".format(entry["fix_by_product_id"])
                    local_cursor.execute(sql)
                    entry["fix_by_product_rn"] = local_cursor.fetchone()[0]
                if entry["fix_by_version_id"] == 0:
                    entry["fix_by_version_rn"] = "Unknown"
                else:
                    sql = """select name from versions where id = {}""".format(entry["fix_by_version_id"])
                    local_cursor.execute(sql)
                    entry["fix_by_version_rn"] = local_cursor.fetchone()[0]
                if entry["fix_by_phase_id"] == 0:
                    entry["fix_by_phase_rn"] = "Unknown"
                else:
                    sql = """select name from phases where id = {}""".format(entry["fix_by_phase_id"])
                    local_cursor.execute(sql)
                    entry["fix_by_phase_rn"] = local_cursor.fetchone()[0]
            
            for entry in Fix_by_Results:
                for key in entry.keys():
                    if entry[key] == None:
                        del entry[key]
            for entry in Fix_by_Results:
                sql = """INSERT INTO bug_fix_by_map
                ({})
                VALUES
                ({})
                ON DUPLICATE KEY UPDATE
                {}
                """.format(
                ','.join(entry.keys()),
                ','.join(map(str,(format_sql(k) for k in entry.values()))),
                ','.join('{}={}'.format(k,format_sql(entry[k])) for k in entry)
                )
                local_cursor.execute(sql)
            
            local_cursor.close()
            local_conn.commit()
            local_conn.close()
            bzdb_cursor.close()
            bzdb_conn.close()
            
        Check_ID(args)
        exit()
    
    try:
        f = open(args.option[0], "r")
    except:
        print "Error: Need to specify option.file location"
        print "python BAR.py option.p"
        sys.stdout.flush()
        exit()
    #Get related option data from option.p
    Raw_OP = []
    Rules = []
    p = re.compile('#(\S|\s)*') #Lines which are documented as comments in option.p
    for key in f:
        if not p.match(key):
            Raw_OP.append(key.rstrip().split(":"))
    
    if args.milestone == True:
        Update_Milestone()
        print "Finish Update Milestone"
        exit()
    
    if args.update == True:
        Periodically_Update_Data = Periodically_Update()
        Update_begin = Periodically_Update_Data[0]
        Update_end = datetime.now().strftime(FMT_YMDHMS)
        Update_bug_id = Periodically_Update_Data[1]
        
        
        
    
    for okey in Raw_OP:
        """
        Try-Except operations for Time section are using to set default value for Rule (option.p)
        """
        try:
            t = time.strptime(okey[4], FMT_YMD)
            bz_date_begin = datetime(t[0], t[1], t[2], 0,0,0).strftime(FMT_YMDHMS)
        except:
            #bz_date_begin = None
            bz_date_begin = Periodically_Update()[0]
        try:
            t = time.strptime(okey[5], FMT_YMD)
            bz_date_end = datetime(t[0], t[1], t[2],23,59,59).strftime(FMT_YMDHMS)
        except:
            bz_date_end = None
        """
        If update is triggered, the begin time and end time should be modified
        """
        if args.update == True:
            bz_date_begin = Update_begin
            bz_date_end = Update_end
        
        Rules.append(Option(
            list(okey[0].split(",")),
            list(okey[1].split(",")), 
            list(okey[2].split(",")),
            list(okey[3].split(",")),
            bz_date_begin, 
            bz_date_end))

    """
    Commented by ShinYeh 0626 since the parsering job are done when options are initialized and loaded
    
    l = []
    for p in args.people:
        l.extend(map(string.strip, p.split(",")))
    args.people = l
    #args.people = option["people"]

    l = []
    for r in args.reports:
        l.extend(map(string.strip, r.split(",")))
    # comment, comments, commented => commented
    args.reports = ["commented" if r.startswith("comment") else r for r in l]

    t = time.strptime(args.date_begin, FMT_YMD)
    bz_date_begin = datetime(t[0], t[1], t[2]).strftime(FMT_YMDHMS)
    t = time.strptime(args.date_end, FMT_YMD)
    bz_date_end = datetime(t[0], t[1], t[2]).strftime(FMT_YMDHMS)
    """
    #gLogger.debug(args._get_kwargs())
    #gOption.update(dict(args._get_kwargs()))
    """ 
    Edited by shinyeht 0625
    Start retrieving information from bugzilla by BAR model
    """
    Query_result={}
    for key in Rules:
        option = key.data
        #option = {'people':key.data["assigned_rn"], 'date_begin':key.data["D_begin"], 'date_end':key.data["D_end"], 'reports': REPORTS, 'product':key.data["product_rn"], 'verbose':3}
        gOption.update(option)
        gOption["reports"] = REPORTS
        gOption["verbose"] = 3
        Query_result[str(key)] = run_report_for(key.data["assigned_rn"], key.data["D_begin"], key.data["D_end"], key.data["product"])
    
    
    """
    Dictionary level
    [Assignee]
    ['outgoing', 'incoming', 'commented', 'backlog', 'guru']
    ['needinfo', 'bug_case_map', 'bug_fix_by_map', 'bugs', 'longdescs']
    [Bug_ID]
    
    End retrieving information, and all the data are saved in Query_result.
    All the database related information are saved in Keep_record.
    The Connection between db and script has cut
    
    Start Run script matching job
    the output will be set in /tmp

    In order to handle '0' key from Bugzilla in versions and phases, I create new items for these two columns
    """
    P = namedtuple("table_versions", "id, name, description, product_id")
    Keep_record["products"][0] = P(0,'Unknown','Not determined',0)
    Keep_record["versions"][0] = P(0,'Unknown','Not determined',0)
    Keep_record["phases"][0] = P(0,'Unknown','Not determined',0)
    
    check_resolved = False
    Total_Result = Match_and_Output(Rules, Query_result, check_resolved)
    
    if args.wo_update_information:
        Update_Information()
    
    if args.update:
        Connect_With_OurDB(Total_Result, Rules, args.update, Update_end)
        """
        Since the bugs would be changed to fixed during the interval, 
        however, our original manuscript can only retrieve the bug status which is not in resolved, closed.
        Therefore, we need to retrieve all the bugID from our own database and retrieve these bugid again.
        """
        Original_Result = Update_With_OriginalID(Total_Result, Update_begin, Update_end, Update_bug_id)
        if Original_Result: #ensure that update_is valiable
            Connect_With_OurDB(Original_Result)
    else:
        Connect_With_OurDB(Total_Result, Rules)
    
    Keep_connect.close()
    print "Finish One Routine"
    

# NOTE:
# -----
# http://ssqian.eng.vmware.com/phpmyadmin/
# host="bz3-db3.eng.vmware.com", port=3306, user="mts", passwd="mts", db="bugzilla"
# http://stackoverflow.com/questions/15465478/update-or-insert-mysql-python
# http://stackoverflow.com/questions/9336270/using-a-python-dict-for-a-sql-insert-statement
# host='localhost', user = 'root', passwd = 'vmware', db= 'TriageRobot'
# Fix By: bug_fix_by_map
# SR: bug_sr_map(obsolated), bug_case_map
# needinfo: needinfo
# Comments: longdescs

#    CPD_GURUS   = ("hosted-cpd-guru", "cpd-platform", "monitor-cpd-guru")
#    MEMBERS_PA  = ("agunathan", "mkuznetsov", "naikd", "nmukuri", "vbhakta", "weili", "zhoum") #liding, fjacob, jliu
#    MEMBERS_BJ  = ("chwang", "hfu", "hillzhao", "letian", "ggong")
#    CORE_GURUS  = ("pit", "usb-sensei", "motley-tools")

# http://stackoverflow.com/questions/1136437/inserting-a-python-datetime-datetime-object-into-mysql
# http://stackoverflow.com/questions/117514/how-do-i-use-timezones-with-a-datetime-object-in-python

