from collections import namedtuple, defaultdict, OrderedDict # Python 2.7
from datetime import datetime, timedelta
class BID_Record:
    def __init__(self):
        self.data={}
        """
        For future extension, I did not initial BID_Record as a pure dict.
        I only implement data as dict.
        If future programmers want to implement some new functions for each record(e.g., data mining), 
        the calculation results can be kept in BID_Record besides of data
        
        In my design, the rule matching module can only interact with BID_Record structure
        The rule matching module will be kept in BAR_Rules.py
        Below variables will be used for recording matching results.
        """
        dic = self.data
        dic["weight"] = int
        dic["highlighted_by"] = []
        dic["case_count"] = int
        
    def Set_Bugs(self, bug_id, assigned_to, assigned_rn, short_desc, product_id, product_rn, category_id, category_rn, component_id, component_rn, bug_status, keywords, resolution, delta_ts, bug_severity, cf_public_severity, cf_attempted, cf_failed, cf_reported_by, cf_eta, priority):
        dic = self.data
        dic["bug_id"] = bug_id
        dic["assigned_to"] = assigned_to
        dic["assigned_rn"] = assigned_rn
        dic["short_desc"] = short_desc
        dic["product_id"] = product_id
        dic["product_rn"] = product_rn
        dic["category_id"] = category_id
        dic["category_rn"] = category_rn
        dic["component_id"] = component_id
        dic["component_rn"] = component_rn
        dic["bug_status"] = bug_status
        dic["keywords"] = keywords
        dic["resolution"] = resolution
        dic["delta_ts"] = delta_ts
        dic["bug_severity"] = bug_severity
        dic["cf_public_severity"] = cf_public_severity
        if cf_attempted:
            dic["cf_attempted"] = cf_attempted
        else:
            dic["cf_attempted"] = 0
        if cf_failed:
            dic["cf_failed"] = cf_failed
        else:
            dic["cf_failed"] = 0
        dic["cf_reported_by"] = cf_reported_by
        if cf_eta:
            dic["cf_eta"] = cf_eta
        
        dic["priority"] = priority
        
    def Set_Bug_fix_by(self, fix_by_product_id, fix_by_product_rn, fix_by_version_id, fix_by_version_rn, fix_by_phase_id, fix_by_phase_rn, fix_by_id):
        dic = self.data
        dic["fix_by_product_id"] = fix_by_product_id
        dic["fix_by_product_rn"] = fix_by_product_rn
        dic["fix_by_version_id"] = fix_by_version_id
        dic["fix_by_version_rn"] = fix_by_version_rn
        dic["fix_by_phase_id"] = fix_by_phase_id
        dic["fix_by_phase_rn"] = fix_by_phase_rn
        dic["fix_by_id"] = fix_by_id

    def Set_Longdescs(self, ld_id, ld_when, ld_who, ld_text):# Comments
        dic = self.data
        dic["ld_id"] = map(int,ld_id)
        dic["ld_when"] = ld_when
        dic["ld_who"] = ld_who
        dic["ld_text"] = ld_text

    def __str__(self):
        return "%s" % (",".join(map(str, [p for p in self.data.items()])))    
        #return "%d %d %s %s %d %s %d %s %d %s %s %s %s %s" % (self.bug_id, self.assigned_to, self.assigned_rn, self.short_desc, self.product_id, self.product_rn, self.category_id, self.category_rn, self.component_id, self.component_rn, self.bug_status, self.keywords, self.resolution, self.delta_ts)


"""
This function turns the rawdata which retrieve from bugzilla into our rawdata model for urgentest
"""

def Original_SQL_data_to_BID_Record(bugs="", fix_by="", longdescs="", conn=""):
    #The input type of bugs should be a list-dictionary [{}]
    sb = BID_Record()
    
    sdata = sb.data
    """
    Process bugs map
    """
    sdata.update(bugs[0])
    if "cf_attempted" not in sdata or not sdata["cf_attempted"]:
        sdata["cf_attempted"] = 0
    if "cf_failed" not in sdata or not sdata["cf_failed"]:
        sdata["cf_failed"] = 0
    if "cf_reported_by" not in sdata or not sdata["cf_reported_by"]:
        sdata["cf_reported_by"] = cf_eta
    
    if not conn:
        log.error("Error in Connection, Oroginal_SQL_data_to_BID_Record BAR.py")
        return "Error in Connection, Oroginal_SQL_data_to_BID_Record BAR.py"
        
    cursor = conn.cursor()
    sql="""
        select profiles.login_name as assigned_rn, 
        products.name as product_rn, 
        categories.name as category_rn, 
        components.name as component_rn
        from profiles, products, categories, components
        where profiles.userid = {}
        and products.id = {}
        and categories.id = {}
        and components.id = {}
    """.format(sdata["assigned_to"], sdata["product_id"], sdata["category_id"], sdata["component_id"])
    
    cursor.execute(sql)
    columns = [column[0] for column in cursor.description]
    rn_results = []
    for row in cursor.fetchall():
            rn_results.append(dict(zip(columns, row)))
    sdata.update(rn_results[0])
    
    """
    Process fix_by_map
    The fix_by_information in sql reuslt is list-dictionary type
    However, in original frame, it is list-type
    Therefore, I use this function to transform the id type into original format
    """
    if fix_by:
        BUG_FIX_BY_KEY = ["fix_by_product_rn", "fix_by_product_id", "fix_by_version_rn", "fix_by_version_id", "fix_by_phase_rn", "fix_by_phase_id", "fix_by_id"]
        for okey in BUG_FIX_BY_KEY:
            sdata[okey] = []
            for ikey in fix_by:
                sdata[okey].append(ikey[okey])
        
    
    """
    Process Comment
    The idea of this part is similar to the previous codes which are processing fix_by_map
    """
    if longdescs:
        LONGDESCS_KEY = ["ld_who", "ld_text", "ld_when", "ld_id"]
        for okey in LONGDESCS_KEY:
            sdata[okey] = []
            for ikey in longdescs:
                sdata[okey].append(ikey[okey])
    
    return sb


"""
The function of Rawdata_to_Saver function is to facilitate the process of combining the rawdata with the database, and regenerating a new data structure for saving information
This function can be replaced by programmers
Shinyeh 0630
#sb-->save_object, db-->database
"""
def Rawdata_to_BID_Record(sb, db):
    result = {}
    
    """
    Retrieve the information from bugs
    """
    for idkey in sb["bugs"]:
        sb_bugs = sb["bugs"][idkey]
        result[idkey] = BID_Record()
        result[idkey].Set_Bugs(sb_bugs[0], 
        sb_bugs[1], db["profiles"][sb_bugs[1]][1],      #assigned_to
        sb_bugs[2],     #short_desc
        sb_bugs[3], db["products"][sb_bugs[3]][1],      #products
        sb_bugs[4], db["categories"][sb_bugs[4]][1],    #categories
        sb_bugs[5], db["components"][sb_bugs[5]][1],    #Components
        sb_bugs[6],     #bugstatus
        sb_bugs[7],     #keywords
        sb_bugs[8],     #resolution
        sb_bugs[9],     #delta_ts
        sb_bugs[10],    #Severity
        sb_bugs[11],    #Public_severity --> Security
        sb_bugs[12],    #cf_attempted
        sb_bugs[13],    #cf_failed
        sb_bugs[14],    #cf_reported_by
        sb_bugs[15],    #cf_eta
        sb_bugs[16]     #Priority
        )
    """
    Retrieve the information from bug_fix_by_map
    """    
    for idkey in sb["bug_fix_by_map"]:
        sb_bugs = sb["bug_fix_by_map"][idkey]
        result[idkey].Set_Bug_fix_by(
        list([p[1] for p in sb_bugs]),
        list([db["products"][p[1]][1] for p in sb_bugs]),
        list([p[2] for p in sb_bugs]),
        list([db["versions"][p[2]][1] for p in sb_bugs]),
        list([p[3] for p in sb_bugs]),
        list([db["phases"][p[3]][1] for p in sb_bugs]),
        list([p[4] for p in sb_bugs]))
    """
    Retrieve the information from commented
    """
    
    
    for idkey in sb["longdescs"]:
        sb_bugs = sb["longdescs"][idkey]
        #print list([p[0] for p in sb_bugs])
        result[idkey].Set_Longdescs(
        list([p[0] for p in sb_bugs]),
        list([p[2] for p in sb_bugs]),
        list([p[3] for p in sb_bugs]),
        list([p[4] for p in sb_bugs]))
    #for idkey in result.keys():
    #    print result[idkey].data["ld_id"]
    return result
    
class Option:
    def __init__(self, 
        assigned_rn="", 
        fix_by_product_rn="", 
        fix_by_version_rn="", 
        product_rn="", 
        D_begin="", 
        D_end=""):#Set default Value
        
        """
        After the after meeting in 7/22 afternoon, the bug_fix_by_product, version, product, and time are never be considered by queries.
        All the query from user will check the assigned_to only.
        If user query a subset, for example, we have queried shinyeht ESX before, the total set of shinyeht will be kept in our local database.
        The assigned_to become the only key to connect with rules.
        However, in order to keep an interface to connect with rules in the future, I did not remove any options since I designed NULL option when I set rules.
        Therefore, the rule in option.p will have five ::::: after each rules, which are represented assigned_to, fix_by_product_rn, fix_by_version_rn, product, date_begin and date_end
        If programmers want to implement subset query in the future for facilitating, it could be complicated by setting minor rule in the option.p.
        Besides, the checking rules module in server.py needs to be modified too.
        
        07/22/2014 shinyeht
        """
        
        
        now = datetime.now()
        FMT_YMD = "%Y-%m-%d"
        FMT_YMDHMS  = "%Y-%m-%d %H:%M:%S"
        #date_end = datetime(now.year, now.month, now.day)
        date_end = datetime(now.year, now.month, now.day,23,59,59)
        """
        if date_end.weekday() > 2: # 2 -> Wed.
            # next Sun
            date_end += timedelta(days=(6-date_end.weekday()))
        else:
            # last Sun
            date_end -= timedelta(days=(date_end.weekday()+1))
        """
        self.data = OrderedDict()
        dic=self.data
        
        if assigned_rn: dic["assigned_rn"] = assigned_rn
        else: dic["assigned_rn"] = "bugs.assigned_to"
        
        
        dic["fix_by_product"] = fix_by_product_rn
        dic["fix_by_version"] = fix_by_version_rn        
        dic["product"] = product_rn
        

        
        if D_begin: dic["D_begin"] = D_begin
        else:#dic["D_begin"] = date_end - timedelta(days=14)
            temp_date_end = date_end - timedelta(days=14)
            temp_date_end = temp_date_end.strftime(FMT_YMDHMS)
            dic["D_begin"] = temp_date_end
            dic["D_begin"] = datetime(now.year, 1, 1).strftime(FMT_YMDHMS)
        if D_end: dic["D_end"] = D_end
        else:#dic["D_end"] = date_end
            temp_date_end = date_end
            temp_date_end = temp_date_end.strftime(FMT_YMDHMS)
            dic["D_end"] = temp_date_end
        
        """
        below parts are using to match gOption design
        """
        #REPORTS = [ "incoming", "outgoing", "commented", "backlog", "guru" ]
        #dic["reports"] = REPORTS
        #dic["verbose"] = 3
