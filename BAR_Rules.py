import os

from BID_Record import *
from collections import namedtuple, defaultdict, OrderedDict # Python 2.7

SCRIPTS_DIR = os.path.abspath(os.path.dirname(__file__))
BAR_OPTION_DIRECTORY = os.path.join(SCRIPTS_DIR, "BAR_option/")
#RULE_PATH = "BAR_option/rule.p"
RULE_PATH = os.path.join(BAR_OPTION_DIRECTORY, "rule.p")

#The conn should be the connection between local computer and bugzilla database
def Urgent_Test(subject, rule, conn, from_web_ui = False):
    Match_Model = Rule_Match(subject, rule, conn)
    """
    Need to implement orderedDict and the related should be kept in the last item,
    since the related test costs lots of time
    """
    sdata = subject.data
    """
    Check weight
    """
    sdata["weight"] = Match_Model.Weight_Calculation()
    """
    Check bug_fix_by_map
    However, if this query is initiated by web_ui, this check should be skipped
    Acutally, after the modification in 07/22, this function could be removed since we not specifiy fix_by_s information in rule.
    However, in order to keep interface open, I did not remove this function
    """
    if not from_web_ui:
        if rule and Match_Model.Match_fix() == False:
            return "Uncared"
            
    Match_Func = OrderedDict([
                ("keywords" , Match_Model.Match_keywords),
                ("parent/child-fix", Match_Model.Match_related),
                ("ETA close", Match_Model.Match_ETA),
                #("duplicate-fix", Match_Model.Match_duplicated)
                ])
    Result = []
    
    for Match_index, Match_func in Match_Func.items():
        function_result = Match_func()
        if function_result:
            Result.append(function_result)
    sdata["highlighted_by"] = ",".join(Result)
    if len(Result) > 0:
        return "Urgent"
    #return result.Match_related() or result.Match_keywords() or result.Match_fix()
    #print subject.data["bug_id"]
    #print
    return "Normal"



class Rule_Match:
    """
    Basic Rule Match object
    Data mining and other mining function can be implemented in this object
    """
    def __init__(self,subject, rule, conn):
        self.subject = subject
        self.rule = rule
        self.conn = conn
    def Weight_Calculation(self):
        sdata = self.subject.data
        """
        The formula of weight calculation can be found in 
        https://wiki.eng.vmware.com/Decision_Tool
        PR weight = class_weight + priority_weight + severity_weight + criteria_weight
        Class -     30% #Actually, Class represent keywords search
        Priority -  10%
        Severity -  25%
        Criteria -  35%
        """
        
        schema = ["case_id"]
        field = ["bug_case_map"]
        
        sql = """select {} from {} where bug_case_map.bug_id = {}""".format(
                        ",".join(schema),
                        ",".join(field),
                        sdata["bug_id"])
                        
        cursor = self.conn.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        Case_Count = len(result)
        
        sdata["case_count"] = Case_Count
        
        
        #Class Weight Calculation
        Class_1 = ["mustfix", "SR", "PMT"]
        Class_2 = ["security"]
        Class_3 = ["Partner", "Ecosystem Engineering", "PE"]
        Test_Result = []
        while True: # Test for Class only run for one-time
            """
            Should not use
                [val for val in Class_1 if val in sdata["keywords"]]
            since the string will be probably match with partial string
            security and mn-st-security
            """
            
            if Case_Count >=1:
                Class_Weight = 1
                break
            
            for val_1 in Class_1:
                for val_2 in list(sdata["keywords"].split(", ")):
                    if val_1 == val_2:
                        Test_Result.append(val_1)
            if Test_Result:
                Class_Weight = 1
                break
            
            for val_1 in Class_2:
                for val_2 in list(sdata["keywords"].split(", ")):
                    if val_1 == val_2:
                        Test_Result.append(val_1)
            if Test_Result:
                Class_Weight = 0.75
                break
            
            for val_1 in Class_3:
                if val_1 in sdata["cf_reported_by"]:
                    Test_Result.append(val_1)
            if Test_Result:
                Class_Weight = 0.75
                break
            
            Class_Weight = 0
            break
        
        #Priority Weight Calculation
        Priority_Point = {"P0":1, "P1":0.5, "P2":0.1}#P3:0
        for key in Priority_Point.keys():
            if key in sdata["priority"]:
                Priority_Weight = Priority_Point[key]
                break
        else:
            Priority_Weight = 0
            
        #Severity Weight Calculation
        Severity_Point = {"catastrophic":1, "critical":0.8, "serious":0.5, "minor":0.1}#Catastrophic:0
        for key in Severity_Point.keys():
            if key in sdata["bug_severity"]:
                Severity_Weight = Severity_Point[key]
                break
        else:
            Severity_Weight = 0
            
        #Criteria 1 SR/PE --> I changed to count case number
        
        #Case Level Point
        Case_Count = len(result)
        if Case_Count <= 5:
            Case_Count_Weight = 0
        elif 5 < Case_Count <=10:
            Case_Count_Weight = 0.2
        elif 10 < Case_Count <=50:
            Case_Count_Weight = 0.6
        elif 50 < Case_Count <=100:
            Case_Count_Weight = 0.9
        else:
            Case_Count_Weight = 1
        #Escalated Level Point
        Escalated = ["escalated-red", "escalated-orange", "escalated-yellow"]
        for key in Escalated:
            if key in sdata["keywords"]:
                Escalated_Weight = 1
                break
        else:
            Escalated_Weight = 0
        SR_PE_Weight = min(Case_Count_Weight + Escalated_Weight, 1) 
        
        #Security Level Point <--> External Severity <--> cf_public_severity
        Security_Point = {"Critical":1, "Important":0.8, "Moderate":0.5}#Low:1
        for key in Security_Point:
            if key in sdata["cf_public_severity"]:
                Security_Weight = Security_Point[key]
                break
        else:
            Security_Weight = 0
        
        #Proactive Criterias
        if sdata["cf_attempted"] != 0:
            PR_Frequency = float(sdata["cf_failed"]) / float(sdata["cf_attempted"])
            if sdata["cf_attempted"] <=1:
                Occurance_Weight = PR_Frequency * 0
            elif 1<sdata["cf_attempted"] <=3:
                Occurance_Weight = PR_Frequency * 0.1
            elif 3<sdata["cf_attempted"] <=10:
                Occurance_Weight = PR_Frequency * 0.2
            else:
                Occurance_Weight = PR_Frequency * 0.35
        else:
            Occurance_Weight = 0
        
        if "cpd-serviceability" in sdata["keywords"]:
            Seviceability = 0.2
        else:
            Seviceability = 0
        if "qanocost" in sdata["keywords"]:
            Qa_no_cost = 0.8
        else:
            Qa_no_cost = 0
        if  sdata["cf_reported_by"] == 'QA' and sdata["bug_severity"] == "catastrophic":
            Qa_blocker = 0.9
        else:
            Qa_blocker = 0
            
        Proactive_Weight = min(max((Occurance_Weight + Seviceability + Qa_no_cost + Qa_blocker),1), Severity_Weight)
        Criteria_Weight = max(SR_PE_Weight, Security_Weight, Proactive_Weight)
        Total_Weight = Class_Weight * 0.3 + Priority_Weight * 0.1 + Severity_Weight * 0.25 + Criteria_Weight * 0.35
        
        
        return Total_Weight
    def Match_ETA(self):
        sdata = self.subject.data
        if "cf_eta" not in sdata.keys() or not sdata["cf_eta"]:
            return
        else:
            now = datetime.now()
            time_diff = sdata["cf_eta"] - datetime.date(datetime(now.year, now.month, now.day))
            if timedelta(7) < time_diff:
                return
            elif timedelta(3) < time_diff <= timedelta(7):
                return "ETA: one week"
            elif timedelta(1) < time_diff <= timedelta(3):
                return "ETA: three days"
            elif timedelta(0) < time_diff <= timedelta(1):
                return "ETA: one day"
            else:
                return "ETA: expired"
        return
            
            
    def Match_keywords(self):
        """
        Match Keyword
        """
        filepath = open(RULE_PATH,"r")
        keywords = []
        for line in filepath:
            keywords.append(line.rstrip())
        Output = [val for val in keywords if val in self.subject.data["keywords"]]
        filepath.close()
        if Output:
            return ",".join(Output)
        else:
            return
    def Match_fix(self):
        """
        Match fix_by map from rule:option.p
        """
        rdata = self.rule.data
        sdata = self.subject.data
        #[''] represents uncaring about the fix_by_product and fix_by_version
        if rdata["fix_by_product"] != [''] and rdata["fix_by_version"] != ['']:
        #Both columns are required by rule, check both columns
            Output_product = [val for val in rdata["fix_by_product"] if val in sdata["fix_by_product_rn"]]
            Output_version = [val for val in rdata["fix_by_version"] if val in sdata["fix_by_version_rn"]]
            if Output_product and Output_version:
                return True
            else:
                return False
        elif rdata["fix_by_product"] != [''] or rdata["fix_by_version"] != ['']:
        #Only one column is required by rule, check one of the rules
            Output_product = [val for val in rdata["fix_by_product"] if val in sdata["fix_by_product_rn"]]
            Output_version = [val for val in rdata["fix_by_version"] if val in sdata["fix_by_version_rn"]]
            if Output_product or Output_version:
                return True
            else:
                return False
        else:
        #Both columns are not required by rule, return True for uncared
            return True
    def Match_related(self):
        """
        Get ID and Start bugzilla query
        Find base and child related
        If base bug or child bug had resolved, this bug should be highlighted
        This matching function costs lots of time.
        Therefore, this match function should be kept in the last order
        """
        cursor = self.conn.cursor()
        sdata = self.subject.data
        
        """
        Before July 2nd, I used this command to query bugzilla.        
        select bug_id, child, base, bug_status, resolution from ( 
        select child, base from related where related.base = 1198236 or related.child = 1198236) as result, bugs 
        where bug_id != 1198236 and (bug_id = result.child or bug_id = result.base)
        
        Actually, this sql command gets a precise answer.
        However, this command costs about 2.2 seconds for Bugzilla to response.
        Therefore, I switch to a fuzzy query command, and this command only cost 0.17 seconds.
        Then, I use python to do a trim job which is faster than query command.

        """
        
        schema = ["bug_id", "bug_status", "resolution"]
        USER_ERROR = ['user error', 'unable to duplicate', 'not a bug', 'wont fix']
        sql = """select {} from ( 
                    select child, base from related where related.base = {} or related.child = {}) as result, bugs 
                    where bug_id = result.child or bug_id = result.base
                        """.format(
                        ",".join(schema),
                        sdata["bug_id"],
                        sdata["bug_id"])
        cursor.execute(sql)
        while True:
            record = cursor.fetchone()
            if not record:
                break
            if record[0] == sdata["bug_id"]:#trim job, the detail can be found below
                continue
            if (record[1] == 'resolved' or record[1] == 'closed' ) and \
               (record[2] not in USER_ERROR):
                return "parent/child-fix"
        return
        """
        NOTE!
        When we query to Bugzilla for the child,base information with bug_id = 1198236,
        we will get this table
        +---------+---------+---------+------------+------------+
        | bug_id  | child   | base    | bug_status | resolution |
        +---------+---------+---------+------------+------------+
        | 1198236 | 1210773 | 1198236 | new        |            |*
        | 1210773 | 1210773 | 1198236 | resolved   | fixed      |
        | 1198236 | 1277178 | 1198236 | new        |            |*
        | 1277178 | 1277178 | 1198236 | new        |            |
        +---------+---------+---------+------------+------------+
        Since 1198236 is a base bug, we only need the information of child bug.
        Therefore, the columns where I labeled with a star can be removed.
        We can use query commands to remove this two columns.
        However, this command will cost lots of time as what I described above
        July 3rd, by ShinYeh
        """
    def Match_duplicated(self):
        """
        This function searches for the duplicated bug
        If the bug_id is shown in the column of dupe_of, this bug could possibly be duplicated by multiple bugs.
        If the bug_id is shown in the column of dupe, this bug duplicates another bug.
        The sql idea of Match_deplucated is similar to the idea of Match_related
        """
        
        cursor = self.conn.cursor()
        sdata = self.subject.data
        
        schema = ["bug_id", "bug_status", "resolution"]
        USER_ERROR = ['user error', 'unable to duplicate', 'not a bug', 'wont fix']
        sql = """select {} from ( 
            select dupe_of, dupe from duplicates where duplicates.dupe_of = {} or duplicates.dupe = {}) as result, bugs 
            where bug_id = result.dupe_of or bug_id = result.dupe""".format(",".join(schema),
                        sdata["bug_id"],
                        sdata["bug_id"])
        cursor.execute(sql)
        
        while True:
            record = cursor.fetchone()
            if not record:
                break
            if record[0] == sdata["bug_id"]:#trim job, the detail can be found below
                continue
            if (record[1] == 'resolved' or record[1] == 'closed' ) and \
               (record[2] not in USER_ERROR):
                return "Duplicated"
        return
        """
        +---------+---------+
        | dupe_of | dupe    |
        +---------+---------+
        | 1198236 | 1169273 |
        +---------+---------+

        """

# NOTE:
# -----
# http://ssqian.eng.vmware.com/phpmyadmin/
# host="bz3-db3.eng.vmware.com", port=3306, user="mts", passwd="mts", db="bugzilla"

