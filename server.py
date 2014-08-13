"""
Need to implement following commands
pip install flask
pip install django
pip install MySQLdb
"""

from Bugzilla_webservice import *
from BAR_Rules import *
from BAR import gRecordSchema
from flask import request
from flask import render_template
from flask import flash
from flask import Flask, session, redirect, url_for, escape, request
from werkzeug.contrib.cache import SimpleCache
import MySQLdb
import hashlib
import os
import time
import logging
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from collections import OrderedDict
from calendar import month_name


ETA_MONTH_CONFIG = 3
"""
    Important, the relativedelta should be modified by config if the user want to modified the eta period
    shinyeh 0718
"""

BUGZILLA_DATABASE_HOST = "bz3-db3.eng.vmware.com"
BUGZILLA_DATABASE_PORT = 3306
BUGZILLA_DATABASE_USER ="mts"
BUGZILLA_DATABASE_PW="mts"
BUGZILLA_DATABASE_DATABASE="bugzilla"
bzdb_conn = MySQLdb.connect(host=BUGZILLA_DATABASE_HOST, port=BUGZILLA_DATABASE_PORT, user=BUGZILLA_DATABASE_USER, passwd=BUGZILLA_DATABASE_PW, db=BUGZILLA_DATABASE_DATABASE)

LOCAL_DATABASE_HOST = "localhost"
LOCAL_DATABASE_PORT = 3306
LOCAL_DATABASE_USER = "root"
LOCAL_DATABASE_PW = "vmware"
LOCAL_DATABASE_DATABASE = "TriageRobot"
local_conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, port=LOCAL_DATABASE_PORT, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)


PATCHTOOL_DATABASE_HOST = "patchtool.eng.vmware.com"
PATCHTOOL_DATABASE_PORT = 3306
PATCHTOOL_DATABASE_USER = "read"
PATCHTOOL_DATABASE_PW = "read"
PATCHTOOL_DATABASE_DATABASE = "rmtool"
pttl_conn = MySQLdb.connect(host=PATCHTOOL_DATABASE_HOST, port=PATCHTOOL_DATABASE_PORT, user=PATCHTOOL_DATABASE_USER, passwd=PATCHTOOL_DATABASE_PW, db=PATCHTOOL_DATABASE_DATABASE)

app = Flask(__name__)
app.secret_key = 'B1Z298g/3y2 R~lHHbjaN]LWX/,?RT'
cache = SimpleCache(default_timeout=300)
BUGZILLA_URL = 'https://bugzilla.eng.vmware.com/xmlrpc.cgi'
BAR_OPTION_DIRECTORY = os.path.join(os.path.abspath(os.path.dirname(__file__)), "BAR_option/")
CUSTOM_OPTION_DIRECTORY = os.path.join(os.path.abspath(os.path.dirname(__file__)), "Custom_Setting/")

BAR_OFILENAME = BAR_OPTION_DIRECTORY + "option.p"
BAR_ADMINFILE = BAR_OPTION_DIRECTORY + "admin.p"

T_ETA_DEFAULT_MESSAGE = """
                Please Check the bug:{}
                This bug is need to set a ETA after Triage-accepted
                https://bugzilla.eng.vmware.com/show_bug.cgi?id={}
                ======The upper part is generated automatically by TriageRobot ======
                """
ETA_DEFAULT_MESSAGE = """
                Please Check the bug:{}
                This bug is already expired
                https://bugzilla.eng.vmware.com/show_bug.cgi?id={}
                ======The upper part is generated automatically by TriageRobot ======
                """
W_U_DEFAULT_MESSAGE = """
                Please Check the bug:{}
                This bug is not updated for a long time
                https://bugzilla.eng.vmware.com/show_bug.cgi?id={}
                ======The upper part is generated automatically by TriageRobot ======
                """
EMAIL_WARNING_MESSAGE = "If you want to send additinal message after default {} format, please type here!"

FMT_YMDHMS  = "%Y-%m-%d %H:%M:%S"

with app.test_request_context('/hello', method='POST'):
    # now you can do something with the request until the
    # end of the with block, such as basic assertions:
    assert request.path == '/hello'
    assert request.method == 'POST'


@app.route('/')
def index():
    return render_template('query.html')

@app.route('/Login', methods=['GET', 'POST'])
def Login():
    """
    This function handles login function.
    The login procedure is connected with bugzilla
    After successfully login, the function will check for the admin privilege and record username into data
    The transmission is crypted, and the password is not recorded in the system
    """
    error = None
    if 'USERPROFILE' in os.environ:
        homepath = os.path.join(os.environ["USERPROFILE"], "Local Settings",
                                "Application Data")
    elif 'HOME' in os.environ:
        homepath = os.environ["HOME"]
    else:
        homepath = ''

    cookie_file = os.path.join(homepath, ".bugzilla-cookies.txt")
    #bugzilla_url = options.bugzilla_url
    server = BugzillaServer(BUGZILLA_URL, cookie_file)
    login_result = server.login(str(request.form["BG_account"]), str(request.form["BG_password"]))
    if not login_result:
        logging.warning("{} fails to login into the bugzilla.".format(str(request.form["BG_account"])))
        return render_template('query.html', error = "Error Account/Password, Please Login again")
        
    
    
    
    
    session['username'] = request.form['BG_account']
    session['password'] = request.form['BG_password']
    
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    cursor = conn.cursor()
    sql="""
        select userid from profiles where login_name = '{}'
        """.format(session["username"])
    cursor.execute(sql)
    profile_number = cursor.fetchone()[0]
    
    
    session['userid'] = profile_number
    session['logged_in'] = True
    
    admin_file_path = open(BAR_ADMINFILE, "r")
    admin_members = []
    for line in admin_file_path:
        admin_members.append(line.rstrip())
    if session['username'] in admin_members:
        session['admin'] = True
    else:
        session['admin'] = False
    
    cache.set('username', str(request.form["BG_account"]))
    cache.set('cookie', cookie_file)
    logging.warning("{} login into the bugzilla successfully.".format(session['username']))
    
    
    return Query()
    #return render_template('query.html')

@app.route('/Logout', methods=['GET', 'POST'])
def Logout():
    """
    This function helps user to log out.
    All the session will be left
    """
    
    try:
        logging.warning("{} logout successfully.".format(session['username']))
    except:
        pass
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('admin', None)
    return render_template('query.html', message = 'You were logged out')



@app.route('/Entries_Processing', methods = ['GET', 'POST'])
def Entries_Processing():
    
    from collections import defaultdict
    """
    This function handles entries_processing.html
    It shows the queried table
    This function also provides the function of add/remove keywords and add comments
    """
    Update_List={}
    
    cookie_file = cache.get('cookie')
    #print cookie_file
    
    #if cookie_file is None:
    #    session['logged_in'] = False
    #    return redirect(url_for('query'))
    server = BugzillaServer(BUGZILLA_URL, cookie_file)
    
    
    
    
    result={}
    
    """
    Retrieve all the bugid in the list
    """
    Bug_ID = []
    for key in request.form.keys():
        if "fix_by_" in key and "id" in key:
            Bug_ID.append(int(request.form[key]))
    
    """
    Retrueve the Old Bug_Fix_By_record from local database
    Then, we would do intersetion and union check to filter which record should be removed.
    """
    sql = """select bug_id, fix_by_product_rn, fix_by_version_rn, fix_by_phase_rn from bug_fix_by_map
        where bug_id in ({})
        """.format(",".join(map(str, Bug_ID)))
    
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    if not conn:
        flash("Fail to Connect my Sql, please try again later")
        return render_template('query.html', error="Fail to Connect MySQL, Please try again later")
    cursor=conn.cursor()
    Database_Bug_ID_Results = bug_fix_by_SQL(sql, cursor)
    
    
    """
    Start parse the request.form
    And build comparison form and remove map
    """
    Local_Bug_ID_Results = {}
    Local_Query_Map=defaultdict(lambda: defaultdict(lambda: defaultdict(str)))
    Local_Remove_Map=defaultdict(lambda: defaultdict(lambda: defaultdict(str)))
    
    for key in Bug_ID:
        Local_Bug_ID_Results[key] = []
    
    for key in request.form.keys():
        if "fix_by_" in key:
            string_split = [int(k) for k in key.split('_') if k.isdigit()]

            fix_id=string_split[0]
            fix_number=string_split[1]
            if "product" in key:#Product
                fix_type="product"
            elif "version" in key:#Version
                fix_type="version"
            elif "phase" in key:#Phase
                fix_type="phase"
            elif "check" in key:#Check --> Remove
                fix_type="check"
                Local_Remove_Map[fix_id][fix_number][fix_type]="Remove" #if the checkbox for marking delete has been checked, it would need to mark for delete below
                continue
            else:
                continue
            Local_Query_Map[fix_id][fix_number][fix_type]=str(request.form[key])
    """
    Remove all the fixnumber record in query record if the check box has been checked
    """
    for ID in Local_Remove_Map:
        for fix_number in Local_Remove_Map[ID]:
            del Local_Query_Map[ID][fix_number]
    """
    Transfer the local query map into the competitive form with Database_Bug_ID_Results
    """
    for ID in Local_Query_Map:
        Local_Bug_ID_Results[ID] = []
        for fix_number in Local_Query_Map[ID]:
            Local_Bug_ID_Results[ID].append(dict(Local_Query_Map[ID][fix_number]))


    """
    Comparison between Local and Database Fix_By_Results
    """
    Fix_By_Add_List=[]
    Fix_By_Remove_List=[]
    for ID in Local_Bug_ID_Results:
        for fix_number in Local_Bug_ID_Results[ID]:
            if fix_number not in Database_Bug_ID_Results[ID]:
                temp={}
                temp["bug_id"] = ID
                temp.update(fix_number)
                Fix_By_Add_List.append(temp)
                
    for ID in Database_Bug_ID_Results:
        for fix_number in Database_Bug_ID_Results[ID]:
            if fix_number not in Local_Bug_ID_Results[ID]:
                temp={}
                temp["bug_id"] = ID
                temp.update(fix_number)
                Fix_By_Remove_List.append(temp)
    
    
    """
    This function transfer all the realname list into id list.
    It also helps user removing all the 0_0_0 case.
    """
    def product_version_phase_realname_to_ID(target_list):
        conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
        if not conn:
            flash("Fail to Connect my Sql, please try again later")
            return render_template('query.html', error="Fail to Connect MySQL, Please try again later")
        cursor=conn.cursor()
        """
        The Following three functions are using for query ID via realname
        The Check Correctness features are implemented after these three function, which are implemented via if-else statement
        """
        def find_product_id(name, cursor):
            if name == '':
                return 0
            sql="""
            select id from products where name = '{}'
            """.format(name)
            cursor.execute(sql)
            try:
                return cursor.fetchone()[0]
            except:
                return None
        def find_version_id(name, cursor, product_id):
            if name == '' or product_id == 0:
                return 0
            sql="""
            select id from versions where name = '{}' and product_id = {}
            """.format(name, product_id)
            cursor.execute(sql)
            try:
                return cursor.fetchone()[0]
            except:
                return None
        def find_phase_id(name, cursor, version_id):
            if name == '' or version_id == 0:
                return 0
            sql="""
            select id from phases where name = '{}' and version_id = {}
            """.format(name, version_id)
            cursor.execute(sql)
            try:
                return cursor.fetchone()[0]
            except:
                return None
        error_message = None
        
        for key in target_list:
            product_id = find_product_id(key["product"],cursor)
            if product_id != None:
                version_id = find_version_id(key["version"],cursor,product_id)
                if version_id != None:
                    phase_id = find_phase_id(key["phase"],cursor,version_id)
                    if not phase_id != None:
                        error_message="phase"
                else:
                    error_message="version"
            else:
                error_message="product"
            
            if error_message:
                logging.warning("{} processings are not approved since the {} name '{}' is wrong.".format(session['username'], error_message, key[error_message]))
                return "Processing are not approved since the {} name '{}' is wrong".format(error_message, key[error_message])
            

            key["product"] = product_id
            key["version"] = version_id
            key["phase"] = phase_id
        #This line will remove all the 0_0_0 case in target_list
        target_list[:] = [x for x in target_list if not (x['product'],x['version'],x['phase'])==(0,0,0)]
        return target_list
    
    #if the return data is list, it is correct. if the return data is string, it is error message
    #Process Add_list
    Record = product_version_phase_realname_to_ID(Fix_By_Add_List)
    if isinstance(Record, str):
        return render_template("query.html", error=Record)
    Fix_By_Add_List = Record
    for key in Fix_By_Add_List:
        if key["bug_id"] not in Update_List.keys():
            Update_List[key["bug_id"]]=True
    
    for key in Fix_By_Add_List:
        fix_by_information=[].append("{}_{}_{}".format(key["product"], key["version"], key["phase"]))
        #server.add_fix_bys(key["bug_id"], fix_by_information)
    
    #Process Remove_list
    Record = product_version_phase_realname_to_ID(Fix_By_Remove_List)
    if isinstance(Record, str):
        return render_template("query.html", error=Record)
    Fix_By_Remove_List = Record
    for key in Fix_By_Remove_List:
        if key["bug_id"] not in Update_List.keys():
            Update_List[key["bug_id"]]=True
    for key in Fix_By_Remove_List:
        fix_by_information=[].append("{}_{}_{}".format(key["product"], key["version"], key["phase"]))
        #server.remove_fix_bys(key["bug_id"], fix_by_information)
    
    """
    Add/Remove keywords and commends
    THe result dictionary is also built in this itinerary
    """
    #print request.form
    for key in request.form.keys():
        if "check_id_" in key: 
            """
            since the there are lots of other keys will be transmited with request.form
            Therefore, I set a "if" to retrieve bug_id value
            """
            check_id = int(key.replace("check_id_",""))
            #This line is using to retrieve the int part of the name (i.e., ID)
            #Process Add Keywords
            if request.form["Add_keywords"] != "":
                Update_List[check_id]=True
                try:
                    result[check_id]["Add_keywords"] = str(request.form["Add_keywords"])
                except:
                    result[check_id]={}
                    result[check_id]["bug_id"] = check_id
                    result[check_id]["Add_keywords"] = str(request.form["Add_keywords"])
                logging.warning("{} add keywords:({}) to {}.".format(session['username'], str(request.form["Add_keywords"]), str(request.form[key])))
                server.add_keywords(check_id, *str(request.form["Add_keywords"]).split(","))
            #Process Remove Keywords
            if request.form["Remove_keywords"] != "":
                Update_List[check_id]=True
                try:
                    result[check_id]["Remove_keywords"] = str(request.form["Remove_keywords"])
                except:
                    result[check_id]={}
                    result[check_id]["bug_id"] = check_id
                    result[check_id]["Remove_keywords"] = str(request.form["Remove_keywords"])
                logging.warning("{} remove keywords:({}) to {}.".format(session['username'], str(request.form["Remove_keywords"]), check_id))
                server.remove_keywords(check_id, *str(request.form["Remove_keywords"]).split(","))

        if "comment_id_" in key:
            if request.form[key] == "":#if the comment is null, just pass it
                continue
            comment_id = int(key.replace("comment_id_",""))
            Update_List[comment_id]=True
            #This line is using to retrieve the int part of the name (i.e., ID)
            try:
                result[comment_id]["comments"] = str(request.form[key])
            except:
                result[comment_id]={}
                result[comment_id]["bug_id"] = comment_id
                result[comment_id]["comments"] = str(request.form[key])
            logging.warning("{} add comments:{} to {}.".format(session['username'], str(request.form[key]), comment_id))
            server.add_comment(comment_id, request.form[key])
    
    """
    After building the dictionary, in order to match the flask format, The process has to rebuild the dictionary into list data type
    """
    results = []
    for key in result:
        results.append(result[key])
    
    """
    Follow the instructions in the metting on 07/22/2014, after each update, the whole record in the local database should be updated again
    """

    ID_String = " ".join(map(str,Update_List.keys()))
    command = "python BAR.py"
    os.system(command + " --ID " + ID_String)
    
    
    return render_template('entries_processing.html', bugs=results, message = "Finish Processing at {}".format(datetime.now().strftime(FMT_YMDHMS)))



@app.route('/query', methods=['GET', 'POST'])
def Query():
    """
    This function queries the database first.
    If there is custom setting in local database, it will fill into respective columns initially.
    """
    
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    cursor = conn.cursor()
    
    sql="""
        select userid from profiles where login_name = '{}'
        """.format(session["username"])
    cursor.execute(sql)
    profile_number = cursor.fetchone()[0]
    
    sql="""
    select * from custom_setting where userid = {}
    """.format(profile_number)
    cursor.execute(sql)
    
    columns = [column[0] for column in cursor.description]
    results = []
    for row in cursor.fetchall():
        results.append(dict(zip(columns, row)))
    if results:
        return render_template('query.html', 
            query_assignee = results[0]["query_assignee"],
            query_product = results[0]["query_product"],
            query_version = results[0]["query_version"],
            query_phase = results[0]["query_phase"]
            )
    else:
        return render_template('query.html')

@app.route('/Show_Entries', methods=['POST'])
def Show_Entries():
    """
    This function processes the quesy and pass the results into show_entries.html
    At first, the function will hash the query into md5.
    Then, the function use this md5 to check with local database.
    If the rule is recorded in local database before, it will retrieve the data in the local database.
    If the rule has not been recorded in local database before, it will retrieve the data from bugzilla first.
    The rule will be recorded in local database after retrieving the data from bugzilla.
    Then, the functino will query the data from out local database again.
    """
    
    """
    Since the request.form['assigned_to'] will probably include ',' and space character, 
    we have to preprocess the request.form['assigned_to']
    e.g., 
    shinyeht,cpd-platform,
    """
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    if not conn:
        flash("Fail to Connect my Sql, please try again later")
        return render_template('query.html', error="Fail to Connect MySQL, Please try again later")
    cursor = conn.cursor()
    
    assigned_to = str(request.form['assigned_to']).rstrip(',')
    """
    Transform assigned_to with alias
    """
    
    processing_assign = assigned_to.split(',')
    
    processing_profile_number = session["userid"]
    processing_profile_results = []
    
    """
    Query the database
    If the key is alias, it would be replaced by the contents of alias.
    If the key is not alias, it would be key itself
    """
    for key in processing_assign:
        sql="""
        select alias_contents from custom_alias
        where userid = {}
        and alias_name = "{}"
        """.format(
                    processing_profile_number,
                    key)
        cursor.execute(sql)
        result = cursor.fetchone()
        if result:
            processing_profile_results.append(result[0])
        else:
            processing_profile_results.append(key)
    """
    Converge the Processing_profile_results into assigned_to again
    
    We have to remove the duplicate profile name
    The below this line is using to remove duplicate
    For example, shinyeht, shinyeht, cpd-platform.
    We should only query shinyeht, cpd-platform
    
    """
    processing_profile_results = ",".join(processing_profile_results)
    processing_profile_results = processing_profile_results.split(',')
    processing_profile_list = []
    for key in processing_profile_results:
        processing_profile_list.append(key.strip())
        
    processing_profile_results = list(set(processing_profile_list))
    
    assigned_to = ",".join(processing_profile_results)
    
    """
    Accordingly, the assigned_to is transfered from alias to normal string
    We have to process cite situation now.
    For example, if there is an alias A, A -> "@:X,Y" , when shinyeht queries A,Z.
    Therefore
        A, Z --> @:X,Y,Z --> a,b,c,Y,Z
    This part would probably cause bugs because of the recursive problem.
    """
    
    processing_cite_list = assigned_to.split(',')
    processing_cite_results = []
    for key in processing_cite_list:
        if "@:" in key:
            if key[0] != "@" and key[1] != ":":
                return render_template('query.html', error = "cite @: using error")
            cite_username = key.replace("@:", "")
            
            sql = """
            select userid from profiles 
            where login_name = '{}'
            """.format(cite_username)
            cursor.execute(sql)
            result = cursor.fetchone()
            if result:
                cite_userid = result[0]
            else:
                return render_template('query.html', error = "error in profile query")
            
            sql="""
            select care_member from custom_setting
            where userid = {}
            """.format(cite_userid)
            cursor.execute(sql)
            result = cursor.fetchone()
            if result:
                cite_contents = result[0]
                processing_cite_results.append(cite_contents)
            else:
                pass
        else:
            processing_cite_results.append(key)
    
    print processing_cite_results
    
    processing_cite_results = ",".join(processing_cite_results)
    processing_cite_results = processing_cite_results.split(',')
    processing_cite_list = []
    for key in processing_cite_results:
        processing_cite_list.append(key.strip())
    processing_cite_results = list(set(processing_cite_list))
    
    assigned_to = ",".join(processing_cite_results)
    

        
    
    
    """
    request.form["assigned_to"] processing finish
    """
    
    """
    Since the request.form['date_begin'] and request.form['date_end'] is in date format.
    We have to preprocess the date format into precise time format for matching 'between' query in mysql
    """
    if request.form['date_begin']!="":
        Date_begin  = "'" + request.form['date_begin'] + " 00:00:00" + "'"
    else:
        Date_begin = "delta_ts"
    if request.form['date_end']!="":
        Date_end    = "'" + request.form['date_end'] + " 23:59:59" + "'"
    else:
        Date_end = "delta_ts"
    
    """
    This line is commented because of the 07/22 meeting.
    This is lines is the first line.
    In the bottom of the code, there is another line which modified Format_Rule.
    The reason and new method are defined in the comment of BAR.py
    #Input_Rule = assigned_to+request.form['fix_by_product']+request.form['fix_by_version']+request.form['product']
    """
    Input_Rule = assigned_to
    Need_Query_List=[]
    
    logging.warning("{} queries for assigned_to:{}\t fix_by_product:{}\t fix_by_version:{}\t product:{}.".format(session['username'], assigned_to, request.form['fix_by_product'], request.form['fix_by_version'], request.form['product']))
    
    
    """
    The following iteration compares each profile name in the query.
    It will pick the queries which are not queried before in order to avoid duplicate queries.
    Needing query profiles will be kepy in Need_Query_List.
    """
    
    for key in str(assigned_to).split(','):
        check_sum = hashlib.md5(key).hexdigest()
        sql = """select md5 from rules where md5 = '{}'""".format(check_sum)
        cursor.execute(sql)
    
        result = cursor.fetchone()
        if not result:
            Need_Query_List.append(key)
    
    """
    This section is used for comparing input name with the database.
    If the user types the wrong name, it would trigger the checking process
    """
    len_input=len(str(assigned_to).split(','))
    
    
    if not len_input:
        logging.warning("{} queries are not approved since the assigned column should not be empty.".format(session['username']))
        return render_template('query.html', error="The assigned column should not be empty.")
    
    
    sql = """select userid from profiles where login_name in ('{}')""".format("','".join(assigned_to.split(',')))
    
    cursor.execute(sql)
    profile_result = cursor.fetchall()
    profile_number = ",".join(map(str, (key[0] for key in profile_result)))
    len_db=len(profile_result)
    
    if len_db != len_input:
        logging.warning("{} queries are not approved since the profile name is unfindable.".format(session['username']))
        return render_template('query.html', error="The profile name {} is unfindable. \n Please corrent your spelling".format(assigned_to))
    
    """
    This section is used for comparing input product name with the database.
    If the user types the wrong name, it would trigger the checking process
    """
    if str(request.form['fix_by_product']) != "":
        len_input=len(str(request.form['fix_by_product']).split(','))
        sql = """select id from products where name in ('{}')""".format("','".join(request.form['fix_by_product'].split(',')))
        cursor.execute(sql)
        fix_by_product_result = cursor.fetchall()
        fix_by_product_number = ",".join(map(str, (key[0] for key in fix_by_product_result)))
        len_db=len(fix_by_product_result)
        len_product = len(fix_by_product_result)
        
        if len_db < len_input:
            logging.warning("{} queries are not approved since the product name is unfindable.".format(session['username']))
            return render_template('query.html', error="The product name is unfindable. \n Please corrent your spelling")
    else:
        """
        In order to match the query column of versions, the name should be product_id first.
        This name should changed to fix_by_product_id after querying versions
        """
        fix_by_product_number = "product_id"
    """
    The version name has not been verified, since the version is hard to checked without auto complete boxes.
    It should be done with multi-level select menu with javascript.
    Because of the drop menu of bugzilla is done by brute-force style, I did not implement this version check in this script.
    """
    if str(request.form['fix_by_version']) != "":
        len_input=len(str(request.form['fix_by_version']).split(','))
        sql = """select id from versions 
        where name in ('{}')
        and product_id in ({})
        """.format("','".join(request.form['fix_by_version'].split(',')),
        fix_by_product_number)
        cursor.execute(sql)
        fix_by_version_result = cursor.fetchall()
        fix_by_version_number = ",".join(map(str, (key[0] for key in fix_by_version_result)))
        len_db=len(fix_by_version_result)
        len_version = len(fix_by_version_result)
        
        if str(request.form['fix_by_version']) != "" and len_db < len_input:
            logging.warning("{} queries are not approved since the version name is unfindable.".format(session['username']))
            return render_template('query.html', error="The version name is unfindable. \n Please corrent your spelling")
    else:
        fix_by_version_number = "version_id"
    
    """
    The processing of phase name is similar to the processing of version name
    """
    if str(request.form['fix_by_phase']) != "":
        len_input=len(str(request.form['fix_by_phase']).split(','))
        sql = """select id from phases 
        where name in ('{}')
        and version_id in ({})
        """.format("','".join(request.form['fix_by_phase'].split(',')),
        fix_by_version_number)
        
        cursor.execute(sql)
        fix_by_phase_result = cursor.fetchall()
        fix_by_phase_number = ",".join(map(str, (key[0] for key in fix_by_phase_result)))
        len_db=len(fix_by_phase_result)
        len_phase = len(fix_by_phase_result)
        
        if str(request.form['fix_by_phase']) != "" and len_db < len_input:
            logging.warning("{} queries are not approved since the phase name is unfindable.".format(session['username']))
            return render_template('query.html', error="The phase name is unfindable. \n Please corrent your spelling")
    else:
        fix_by_phase_number = "phase_id"
    
    
    
    
    
    
    """
    Change the product, version and phase number to "fix_by_product_xx"
    """
    if str(request.form['fix_by_product']) == "":
        fix_by_product_number = "fix_by_product_id"
    if str(request.form['fix_by_version']) == "":
        fix_by_version_number = "fix_by_version_id"
    if str(request.form['fix_by_phase']) == "":
        fix_by_phase_number = "fix_by_phase_id"
    
    """
    If the product number is larger than two, the length of version can only be zero.
    """
    if request.form['fix_by_version'] != "" or request.form['fix_by_phase'] != "":
        if request.form['fix_by_product'] == "" or len_product > 1:
            logging.warning("{} queries are not approved since there is more or less than one parameter in product column when version parameter is set".format(session['username']))
            return render_template('query.html', error="The version can only be set when there is only one parameter in product column")
    """
    """
    
    cursor.close()
    conn.close()
    
    """
    If the rule is a new one, the server will triger BAR.py to do another query from Bugzilla.
    This is a quick update. Therefore, I only implement one rule in this update.
    The information of versions, products and profiles are not updated during this time.
    This design probably will cause error since the profiles in our databases are not the latest.
    If the query contains the latest profiles, it would cause error.
    The solution is to trigger update information every 15 minutes.
    """
    for key in Need_Query_List: #This is a new rule
        o_filename = BAR_OFILENAME;
        check_sum = hashlib.md5(key).hexdigest()
        filename = BAR_OPTION_DIRECTORY+check_sum+".p";
        command = "python BAR.py";
        
        """
        This line is commented because of the 07/22 meeting.
        This is lines is the second line.
        In the bottom of the code, there is another line which modified Input_Rule.
        The reason and new method are defined in the comment of BAR.py
        # Format_Rule=assigned_to+":"+
        request.form['fix_by_product']+":"+
        request.form['fix_by_version']+":"+
        request.form['fix_by_phase']+":"+
        request.form['product']+"::\n"
        """
        Format_Rule=key+":"+":"+":"+"::\n"
        fp = open(filename, 'w')
        fp.write(Format_Rule)
        fp.close()
        fp = open(o_filename, 'a')
        fp.write(Format_Rule)
        fp.close()
        os.system(command + " --option " + filename + " --wo_update_information " + " --update " + " --full ")
        os.system("rm " + filename)
    
    """
    This should be modified to match the database
    """
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    
    
    
    people = "','".join(assigned_to.split(','))
        
    sql = """SELECT * from bugs 
    where assigned_to in ({}) 
    and delta_ts between {} and {}
    and keywords not like "%triage-accepted%"
    ORDER by highlighted_by DESC, weight DESC, bug_id""".format(
    profile_number,
    Date_begin, 
    Date_end)
    
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [column[0] for column in cursor.description]
    impure_results = []
    for row in cursor.fetchall():
        impure_results.append(dict(zip(columns, row)))
    
    """
    This process should be done twice since if we only do the first round, 
    we can only retrieve the bug_fix_by_map results which are related to the product, version and phase information.
    However, if this bug contains multiple fix_by_information, we want to show all the bug_fix_by_information of this bug.
    """    
    if impure_results:
        sql = """select bug_id, fix_by_product_rn, fix_by_version_rn, fix_by_phase_rn from bug_fix_by_map
        where bug_id in ({})
        and fix_by_product_id in ({})
        and fix_by_version_id in ({})
        and fix_by_phase_id in ({})
        order by bug_id""".format(",".join(str(k["bug_id"]) for k in impure_results),
        fix_by_product_number,
        fix_by_version_number,
        fix_by_phase_number)
        
        bug_fix_by_results = bug_fix_by_SQL(sql, cursor)
    else:
        bug_fix_by_results = []
   
    """
    We use this iteration to get all the id, and use another bug_fix_by_SQL to search all the ID_related information.
    In the future, if you only want to retrieve the fix_by_s information related to specific version,
    this parts of code can be removed directly without causing errors.
    Remove Start from here!!!
    """
    ID_list=[]
    for key in impure_results:
        if key["bug_id"] in bug_fix_by_results.keys():
            ID_list.append(key["bug_id"])
    
    if ID_list: #in order to avoud quering with a null list
        sql = """select bug_id, fix_by_product_rn, fix_by_version_rn, fix_by_phase_rn from bug_fix_by_map
        where bug_id in ({})
        order by bug_id""".format(",".join(map(str, ID_list)))
        bug_fix_by_results = bug_fix_by_SQL(sql, cursor)
    
    """
    Remove Finish Here!!!
    """
    
    
    
    
    """
    The bugs-results have to be purified by bug_fix_by_map since we only use assigned_id to query bugs-results
    There are bugs which are not having the correct fix_by_entries in the impure_results conta
    """
    Pure_results=[]
    for key in impure_results:
        if key["bug_id"] in bug_fix_by_results.keys():
            Pure_results.append(key)
    
    cursor.close()
    conn.close()
    
    """
    Finish Bugs_table generation.
    The below parts are using to generate charts for triage-accepted
    In order to match the form of bugzilla database, I change the name of variable to query.
    The minimal unit is version, if programmers want to implement phase only, the code is similar to the product and version
    """
    
    bz_query_product = "bug_fix_by_map.product_id" if fix_by_product_number == "fix_by_product_id" else fix_by_product_number
    bz_query_version = "bug_fix_by_map.version_id" if fix_by_version_number == "fix_by_version_id" else fix_by_version_number
        
    
    sql = """
    select delta_ts from bugs, bug_fix_by_map
    where assigned_to in ({}) 
    and delta_ts>'{}' 
    and keywords like '%triage-accepted%'
    and bug_fix_by_map.bug_id = bugs.bug_id
    and bug_fix_by_map.product_id = {}
    and bug_fix_by_map.version_id = {}
    """.format(profile_number, 
    date.today() - relativedelta(months = 6) + relativedelta(day=1),
    bz_query_product,
    bz_query_version,
    )

    try:
        global bzdb_conn
        cursor = bzdb_conn.cursor()
        cursor.execute(sql)
    except (AttributeError, MySQLdb.OperationalError):
        logging.warning("Bugzilla Database Reconnect")
        bzdb_conn = MySQLdb.connect(host=BUGZILLA_DATABASE_HOST, port=BUGZILLA_DATABASE_PORT, user=BUGZILLA_DATABASE_USER, passwd=BUGZILLA_DATABASE_PW, db=BUGZILLA_DATABASE_DATABASE)
        cursor = bzdb_conn.cursor()
        cursor.execute(sql)
    
    date_bins = OrderedDict([(date.today() - relativedelta(months = key) + relativedelta(day = 1), 0) for key in range(0,7)])
    
    while True:
        record = cursor.fetchone()
        if not record:
            break
        query_date = record[0]
        for key in range(0,7):
            Up = datetime.now() - relativedelta(months = key) + relativedelta(day=1, months=+1) #The last day+1
            Bot = datetime.now() - relativedelta(months = key) + relativedelta(day=1, days=-1)  #The first day-1
            if  Up > query_date > Bot:
                date_bins[date.today() - relativedelta(months = key) + relativedelta(day = 1)] += 1
                break
    date_results=[]
    for key in date_bins:
        date_results.append(dict(Month = month_name[key.month], Value = date_bins[key]))
    date_results.reverse()
    
    
    milestone_results=[]
    if request.form['fix_by_product'] != "" and request.form['fix_by_version'] != "":
        milestone_results = milestone_check(fix_by_product_number, fix_by_version_number)
        milestone_flag = True
    else:
        milestone_flag = False
        
    
    return render_template('show_entries.html', 
    bugs = Pure_results, 
    fix_by=bug_fix_by_results, 
    triage_date = date_results, 
    assigned = assigned_to, 
    milestone_flag = milestone_flag, 
    milestone_results = milestone_results, 
    query = request.form)

@app.route('/Admin_Custom_Webpage', methods=['GET', 'POST'])
def Admin_Custom_Webpage():
    """
    This function is a intro webpage, and this function handles admin_custom_webpage.html
    """
    return render_template('admin_custom.html')

@app.route('/Admin_Custom_Triage_Chart', methods=['GET', 'POST'])
def Admin_Custom_Triage_Chart():
    
    """
    This function is using to made chart of triage-accepted chart
    Besides, in order to get weight and all the bugs(included resolved and closed), we have to do realtime calculation.
    Therefore, we did not query bug from local database, we query all the data from bugzilla
    """
    
    if request.method == 'GET':
        return render_template('admin_custom_triage_chart.html')
    
    
    """
    Connect to the local database
    If fail to connect to local database, return fail message
    The top parts of this function are similar to the show_entries function.
    However, I did not process them as a function since the function will make the code unreadable
    """
    
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    if not conn:
        flash("Fail to Connect my Sql, please try again later")
        return render_template('admin_custom_triage_chart.html', error="Fail to Connect MySQL, Please try again later")
    cursor = conn.cursor()
    
    """
    Check for the input profile name
    """
    assigned_to = request.form['query_user'].rstrip(',')
    
    len_input=len(str(assigned_to).split(','))
    if not len_input:
        logging.warning("{} queries are not approved since the assigned column should not be empty.".format(session['username']))
        return render_template('admin_custom_triage_chart.html', error="The assigned column should not be empty.")
    
    sql = """select userid from profiles where login_name in ('{}')""".format("','".join(assigned_to.split(',')))
        
    cursor.execute(sql)
    profile_result = cursor.fetchall()
    profile_number = ",".join(map(str, (key[0] for key in profile_result)))
    len_db=len(profile_result)
    if len_db != len_input:
        logging.warning("{} queries are not approved since the profile name is unfindable. The function location is in admin_custom_triage_chart ".format(session['username']))
        return render_template('admin_custom_triage_chart.html', error="The profile name is unfindable. \n Please corrent your spelling")
    
    
    """
    Handle and chart the bugs which are triage-accepted by the user
    There are two similar charting codes in the below parts.
    The only difference is the sql code.
    However, I still did not implement them into a function.
    I thought that the charting function is always different between each other.
    It is coincidence that we have two similar codes.
    The programmers could implement them into function in the future if they prefer 
    """
    
    sql = """
        select bug_when, bug_id from bugs_activity where who in ({}) and bug_when>'{}' and fieldid = 12 and added = 'triage-accepted'
        """.format(profile_number, date.today() - relativedelta(months = 6) + relativedelta(day=1))
    """
    Connect to bugzilla
    """
    try:
        global bzdb_conn
        cursor = bzdb_conn.cursor()
        cursor.execute(sql)
    except (AttributeError, MySQLdb.OperationalError):
        logging.warning("Bugzilla Database Reconnect")
        bzdb_conn = MySQLdb.connect(host=BUGZILLA_DATABASE_HOST, port=BUGZILLA_DATABASE_PORT, user=BUGZILLA_DATABASE_USER, passwd=BUGZILLA_DATABASE_PW, db=BUGZILLA_DATABASE_DATABASE)
        cursor = bzdb_conn.cursor()
        cursor.execute(sql)
    """
    Set a orderdict, and user this dictionary as bins.
    Then, we put all the bugs into each bin.
    """    
    date_bins = OrderedDict([(date.today() - relativedelta(months = key) + relativedelta(day = 1), 0) for key in range(0,7)])
    #Use this list to keep all the id record
    TA_by_ID_list=[]
    while True:
        TA_by_record = cursor.fetchone()
        if not TA_by_record:
            break
        query_date = TA_by_record[0]
        TA_by_ID_list.append(TA_by_record[1])
        for key in range(0,7):
            Up = datetime.now() - relativedelta(months = key) + relativedelta(day=1, months=+1) #The last day+1
            Bot = datetime.now() - relativedelta(months = key) + relativedelta(day=1, days=-1)  #The first day-1
            if  Up > query_date > Bot:
                date_bins[date.today() - relativedelta(months = key) + relativedelta(day = 1)] += 1
                break
    TA_by_results=[]
    for key in date_bins:
        TA_by_results.append(dict(Month = month_name[key.month], Value = date_bins[key]))
    """
    The results have to be reversed in order to match January, Feburary....July Order
    """
    TA_by_results.reverse()
    
    
    
    """
    Handle and chart the bugs which are triage-accepted and are owned by the user
    """
    
    sql = """
        select delta_ts, bug_id from bugs where assigned_to in ({}) and delta_ts>'{}' and keywords like '%triage-accepted%'
        """.format(profile_number, date.today() - relativedelta(months = 6) + relativedelta(day=1))
    
    cursor.execute(sql)
    date_bins = OrderedDict([(date.today() - relativedelta(months = key) + relativedelta(day = 1), 0) for key in range(0,7)])
    TA_Own_ID_list = []
    while True:
        TA_Own_record = cursor.fetchone()
        if not TA_Own_record:
            break
        query_date = TA_Own_record[0]
        TA_Own_ID_list.append(TA_Own_record[1])
        for key in range(0,7):
            Up = datetime.now() - relativedelta(months = key) + relativedelta(day=1, months=+1) #The last day+1
            Bot = datetime.now() - relativedelta(months = key) + relativedelta(day=1, days=-1)  #The first day-1
            if  Up > query_date > Bot:
                date_bins[date.today() - relativedelta(months = key) + relativedelta(day = 1)] += 1
                break
    TA_Own_results=[]
    for key in date_bins:
        TA_Own_results.append(dict(Month = month_name[key.month], Value = date_bins[key]))
    TA_Own_results.reverse()
    
    
    """
    Handle TA_by_results datatable
    We have to converge the datatype from BID_record into list for flask and jinja2
    """
    TA_by_data_list = []
    if TA_by_ID_list:
        TA_by_data = id_to_full_data(TA_by_ID_list)
        for key in TA_by_data.keys():
            TA_by_data[key].data["fix_by_product_rn"] = TA_by_data[key].data["fix_by_product_rn"][0]
            TA_by_data[key].data["fix_by_version_rn"] = TA_by_data[key].data["fix_by_version_rn"][0]
            TA_by_data[key].data["fix_by_phase_rn"] = TA_by_data[key].data["fix_by_phase_rn"][0]
            TA_by_data_list.append(TA_by_data[key].data)
    """
    Handle TA_Own_results datatable
    """
    TA_Own_data_list = []
    if TA_Own_ID_list:
        TA_Own_data = id_to_full_data(TA_Own_ID_list)
        for key in TA_Own_data.keys():
            TA_Own_data[key].data["fix_by_product_rn"] = TA_Own_data[key].data["fix_by_product_rn"][0]
            TA_Own_data[key].data["fix_by_version_rn"] = TA_Own_data[key].data["fix_by_version_rn"][0]
            TA_Own_data[key].data["fix_by_phase_rn"] = TA_Own_data[key].data["fix_by_phase_rn"][0]
            TA_Own_data_list.append(TA_Own_data[key].data)
    
    
    
    
    return render_template('admin_custom_triage_chart.html', TA_by_results = TA_by_results, TA_Own_results = TA_Own_results, chart_flag = True, assigned = assigned_to, TA_by_data = TA_by_data_list, TA_Own_data = TA_Own_data_list)

@app.route('/Admin_Custom_Update', methods=['GET', 'POST'])
def Admin_Custom_Update():
    filename = BAR_OFILENAME;
    command = "python BAR.py "
    os.system(command + " --option " + filename + " --wo_update_information" + " --update")
    return render_template('admin_custom.html', message = "Finish Update at {}".format(datetime.now().strftime(FMT_YMDHMS)))
    

@app.route('/Custom_Webpage', methods=['GET', 'POST'])
def Custom_Webpage():
    return render_template('custom_list.html')

@app.route('/Custom_Alias', methods=['GET', 'POST'])
def Custom_Alias():
    from collections import defaultdict
    
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    cursor = conn.cursor()
    
    profile_number = session["userid"]
    
    
    if request.method=="POST":
                
        New_Alias_Map=defaultdict(lambda: defaultdict(str))
        Old_Alias_Map=defaultdict(lambda: defaultdict(str))
        Del_List = []
        
        for key in request.form.keys():
            if "name_" in key:
                rule_id = key.replace("name_", "")#Remove the Prefix of key
                New_Alias_Map[rule_id]["alias_name"] = str(request.form[key])
            elif "contents_" in key:
                rule_id = key.replace("contents_", "")
                New_Alias_Map[rule_id]["alias_contents"] = str(request.form[key])
            elif "del_" in key:
                rule_md5 = key.replace("del_", "")
                Del_List.append(rule_md5)
            elif "modify_" in key:
                rule_md5 = key.replace("modify_", "")
                Old_Alias_Map[rule_md5]["alias_contents"] = str(request.form[key])
                Old_Alias_Map[rule_md5]["md5"] = rule_md5
        
        """
        Rebuild New_Alias_Map into Update_Map
        """
        Update_Map = []
        for key in New_Alias_Map:
            New_Alias_Map[key]["userid"] = profile_number
            alias_name = New_Alias_Map[key]["alias_name"]
            New_Alias_Map[key]["md5"] = hashlib.md5(alias_name + str(profile_number)).hexdigest()
            Update_Map.append(dict(New_Alias_Map[key]))
            
        
        
        """
        Since the code modifies all the rules every time, the delete code should be executed below modify.
        Otherwise, the delete progress will be failed
        """
        
        """
        Rebuild Old_Alias_Map into Modify_Map
        """
        Modify_Map = []
        for key in Old_Alias_Map:
            Modify_Map.append(dict(Old_Alias_Map[key]))
        
        for entry in Modify_Map:
            sql="""
            INSERT INTO custom_alias ({})
            value ({}) 
            ON DUPLICATE KEY UPDATE
            {}
            """.format(
                ','.join(entry.keys()),
                ','.join(map(str,(format_sql(k) for k in entry.values()))),
                ','.join('{}={}'.format(k,format_sql(entry[k])) for k in entry)
            )
            cursor.execute(sql)
        
        
        if Del_List:
            sql="""
            delete from custom_alias where md5 in ({})
            """.format(",".join(map(format_sql,Del_List)))
            cursor.execute(sql)
        
        for entry in Update_Map:
            if entry["alias_name"]=="" or entry["alias_contents"]=="":
                continue
            sql="""
                INSERT INTO custom_alias
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
            cursor.execute(sql)
        #cursor.close()
        conn.commit()
        #conn.close()
        
    sql="""
    select * from custom_alias where userid = {}
    ORDER BY alias_name
    """.format(profile_number)
    
    cursor.execute(sql)
    columns = [column[0] for column in cursor.description]
    results = []
    for row in cursor.fetchall():
        results.append(dict(zip(columns, row)))
    
    cursor.close()
    conn.close()
    print results
    return render_template('custom_alias.html', alias = results)

@app.route('/Custom_Setting', methods=['GET', 'POST'])
def Custom_Setting():
    """
    This function handles the custom setting which is saved in local database.
    The format of the setting could be found in Custom_Setting_Format.py
    I use a dictionary to save all the data which is named as custom_setting.data
    """
    from Custom_Setting_Format import Custom_Setting
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    cursor = conn.cursor()
    
    if request.method == 'GET':
        """
        In get method, the program queries the data from database
        """

        profile_number = session["userid"]
        
        sql="""
        select * from custom_setting where userid = {}
        """.format(profile_number)
        cursor.execute(sql)
        
        columns = [column[0] for column in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        if results:
            return render_template('custom_setting.html', 
                care_member = results[0]["care_member"],
                query_assignee = results[0]["query_assignee"],
                query_product = results[0]["query_product"],
                query_version = results[0]["query_version"],
                query_phase = results[0]["query_phase"],
                email_notification = results[0]["email_notification"]
                )
        else:
            return render_template('custom_setting.html')
    elif request.method == 'POST':
        
        """
        In post method, the program updates the data in database, and return the latest values to the original webpage
        In comparison with get method, in post method, we need to check the correctness of input
        Checking Correctness is withdraw now since the time issue.
        Without checking correctness here, the program can still execute properly because of the checking correctness in show_entries function
        """
        sql="""
        select userid from profiles where login_name = '{}'
        """.format(session["username"])
        cursor.execute(sql)
        profile_number = cursor.fetchone()[0]
        
        userid = profile_number
        care_member = str(request.form["care_member"])
        query_assignee = str(request.form["query_assignee"])
        query_product = str(request.form["query_product"])
        query_version = str(request.form["query_version"])
        query_phase = str(request.form["query_phase"])
        error=""
        if request.form["email_notification"]:
            try:
                email_notification = int(request.form["email_notification"])
                if not isinstance(email_notification, int) or email_notification < 0 :
                    error = "Email notification should be integer >= 0"
            except:
                error = "Email notification should be integer >= 0"
            """
            email_notification should >=0 and should be integer
            """
        else:
            email_notification = 0
        """
        @: (Cite symbol should not be used in care_member to avoid recursive checking)
        """
        if "@:" in care_member:
            error = "@: cite symbol should not be used in care_member"
        
        if error:
            sql="""
            select * from custom_setting where userid = {}
            """.format(profile_number)
            cursor.execute(sql)
            
            columns = [column[0] for column in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            if results:
                return render_template('custom_setting.html', 
                    care_member = results[0]["care_member"],
                    query_assignee = results[0]["query_assignee"],
                    query_product = results[0]["query_product"],
                    query_version = results[0]["query_version"],
                    query_phase = results[0]["query_phase"],
                    email_notification = results[0]["email_notification"],
                    error = error
                    )
            else:
                return render_template('custom_setting.html', error=error)
        
        #purify care_member
        #reduce ',' or space
        
        care_list=[]
        for key in care_member.strip(',').split(','):
            temp = key.strip(',')
            temp = temp.strip()
            care_list.append(temp)
        care_member = ",".join(care_list)
        
        
        C_S_Temp = Custom_Setting(
                        userid = userid,
                        care_member = care_member, 
                        query_assignee = query_assignee,
                        query_product = query_product,
                        query_version = query_version,
                        query_phase = query_phase,
                        email_notification = email_notification)
        
        sql="""
        INSERT INTO custom_setting
                    ({})
                    VALUES
                    ({})
                    ON DUPLICATE KEY UPDATE
                    {}
                    """.format(
                    ','.join(C_S_Temp.data.keys()),
                    ','.join(map(str,(format_sql(k) for k in C_S_Temp.data.values()))),
                    ','.join('{}={}'.format(k,format_sql(C_S_Temp.data[k])) for k in C_S_Temp.data)
                    )
        cursor.execute(sql)
        cursor.close()
        conn.commit()
        conn.close()
        return render_template('custom_setting.html', 
                care_member = care_member,
                query_assignee = query_assignee,
                query_product = query_product,
                query_version = query_version,
                query_phase = query_phase,
                email_notification = email_notification,
                message = "Finish Custom Editing at {}".format(datetime.now().strftime(FMT_YMDHMS))
                )

@app.route('/Chrome_Extension_Bugs', methods=['GET', 'POST'])
def Chrome_Extension_Bugs():
    
    ID = int(request.form["id"])
    result = id_to_full_data([ID])
    
    return str(result[ID].data["weight"])+"_"+str(result[ID].data["highlighted_by"])
    

@app.route('/Chrome_Extension/<int:number>', methods=['GET', 'POST'])
def Chrome_Extension(number):

    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    cursor = conn.cursor()
    
    sql = """ select bug_id from bugs where bug_id = {}
    """.format(str(number))
    cursor.execute(sql)
    result = cursor.fetchone()
    if not result:
        ID_String = str(number)
        command = "python BAR.py"
        os.system(command + " --ID " + ID_String)
    
    
    bzdb_conn = MySQLdb.connect(host=BUGZILLA_DATABASE_HOST, port=BUGZILLA_DATABASE_PORT, user=BUGZILLA_DATABASE_USER, passwd=BUGZILLA_DATABASE_PW, db=BUGZILLA_DATABASE_DATABASE)
    cursor = bzdb_conn.cursor()        
    
    sql = """select assigned_to from bugs where bug_id = {}
    """.format(str(number))
    
    cursor.execute(sql)
    profile_number = cursor.fetchone()[0]
    
    sql = """select login_name, realname from profiles where userid= {}
    """.format(profile_number)
    
    cursor.execute(sql)
    profile_data = cursor.fetchone()
    assigned = str(profile_data[0]) + " - (" + str(profile_data[1]) + ")"
    
    sql = """
        select delta_ts from bugs where assigned_to in ({}) and delta_ts>'{}' and keywords like '%triage-accepted%'
        """.format(profile_number, date.today() - relativedelta(months = 6) + relativedelta(day=1))
    
    cursor.execute(sql)
    
    date_bins = OrderedDict([(date.today() - relativedelta(months = key) + relativedelta(day = 1), 0) for key in range(0,7)])
    while True:
        record = cursor.fetchone()
        if not record:
            break
        query_date = record[0]
        for key in range(0,7):
            Up = datetime.now() - relativedelta(months = key) + relativedelta(day=1, months=+1) #The last day+1
            Bot = datetime.now() - relativedelta(months = key) + relativedelta(day=1, days=-1)  #The first day-1
            if  Up > query_date > Bot:
                date_bins[date.today() - relativedelta(months = key) + relativedelta(day = 1)] += 1
                break
    TA_Own_results=[]
    for key in date_bins:
        TA_Own_results.append(dict(Month = month_name[key.month], Value = date_bins[key]))
    TA_Own_results.reverse()
    
    
    
    return render_template('Chrome_Extension.html', TA_Own_results = TA_Own_results, assigned = assigned)
    
    
    labels = '"' + '","'.join(k["Month"] for k in TA_Own_results) + '"'
    data = ",".join(map(str, (k["Value"] for k in TA_Own_results)))
    
    
    
    
    #Return a small webpage which contains two figures
@app.route('/Admin_Custom_Email', methods=['GET', 'POST'])
def Admin_Custom_Email():
    """
    This function handles the webpage of admin_custom_email.html
    This function sends several types of sql and show the tables
    In 0718, Shin-Yeh implemented three types of email.
    1. Send email to ask adding ETA when the bug is triage-accepted
    2. Send email to ask checking ETA since the bug is expired or in rush
    3. Send email to ask updateing since the bug is not updated for a long time
    """
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    
    """
    The first sql is aimed to find the bugs which are already triage-accepted but withoug setting ETA
    """
    
    sql = """SELECT * from bugs 
        where keywords like "%triage-accepted%"
        and cf_eta is NULL
        ORDER by highlighted_by DESC, weight DESC, bug_id"""
        
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [column[0] for column in cursor.description]
    T_ETA_bug_results = []
    for row in cursor.fetchall():
        T_ETA_bug_results.append(dict(zip(columns, row)))
            
    sql = """select bug_id, fix_by_product_rn, fix_by_version_rn, fix_by_phase_rn from bug_fix_by_map
        where bug_id in ({})
        order by bug_id""".format(",".join(str(k["bug_id"]) for k in T_ETA_bug_results))
    T_ETA_bug_fix_by_results = bug_fix_by_SQL(sql, cursor)
    
    """
    The second sql is aimed to find the bugs which are in ETA problems.
    For example, ETA: expired, ETA: one week, ETA one days.....
    """   
    
    sql = """SELECT * from bugs 
        where highlighted_by like "%ETA:%"
        ORDER by highlighted_by DESC, weight DESC, bug_id"""
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [column[0] for column in cursor.description]
    ETA_bug_results = []
    for row in cursor.fetchall():
        ETA_bug_results.append(dict(zip(columns, row)))
            
    sql = """select bug_id, fix_by_product_rn, fix_by_version_rn, fix_by_phase_rn from bug_fix_by_map
        where bug_id in ({})
        order by bug_id""".format(",".join(str(k["bug_id"]) for k in ETA_bug_results))
    
    ETA_bug_fix_by_results = bug_fix_by_SQL(sql, cursor)
    
    
    """
    The third sql is aimed to find the bugs which are not updated for a long time
    The number is set in admin_config_webpage
    """
    sql = """select * from bugs
    where delta_ts < '{}'
    ORDER by highlighted_by DESC, weight DESC, bug_id
    """.format(date.today() - relativedelta(months = ETA_MONTH_CONFIG))
    
    """
    Important, the relativedelta should be modified by config if the user want to modified the eta period
    shinyeh 0718
    """
    
    
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [column[0] for column in cursor.description]
    W_U_bug_results = []
    for row in cursor.fetchall():
        W_U_bug_results.append(dict(zip(columns, row)))
    
    sql = """select bug_id, fix_by_product_rn, fix_by_version_rn, fix_by_phase_rn from bug_fix_by_map
        where bug_id in ({})
        order by bug_id""".format(",".join(str(k["bug_id"]) for k in W_U_bug_results))
    W_U_bug_fix_by_results = bug_fix_by_SQL(sql, cursor)
    
    
    T_ETA_Message = EMAIL_WARNING_MESSAGE.format("'Should After ETA After Triage-accepted'")
    ETA_Message = EMAIL_WARNING_MESSAGE.format("'ETA Expired'")
    W_U_Message = EMAIL_WARNING_MESSAGE.format("'Longtime Without Update'")
    
    
    
    return render_template('admin_custom_email.html', 
    T_ETA_bug_results = T_ETA_bug_results, 
    T_ETA_bug_fix_by_results = T_ETA_bug_fix_by_results,
    T_ETA_Message = T_ETA_Message,
    ETA_bug_results = ETA_bug_results, 
    ETA_bug_fix_by_results = ETA_bug_fix_by_results,
    ETA_Message = ETA_Message,
    W_U_bug_results = W_U_bug_results,
    W_U_bug_fix_by_results = W_U_bug_fix_by_results,
    W_U_Message = W_U_Message)
    
    
@app.route('/Admin_Email_Processing', methods=['GET', 'POST'])
def Admin_Email_Processing():
    """
    This function handles the post action of admin_custom_email.html.
    This function will send email to the correspond assignee with correspond comments
    The name of the variables in this function should be identical to the namr of the variables in Admin_Custom_Email
    """
    from_addr = session["username"] + "@vmware.com"
    
    for key in request.form.keys():
        if "T_ETA_check" in key:
            Bug_id = str(request.form[key])
            to_addr = str(request.form[Bug_id]) + "@vmware.com"
            subject = "Please Check the bug:{}".format(Bug_id)
            
            
            message = T_ETA_DEFAULT_MESSAGE.format(Bug_id, Bug_id)
            if request.form["T_ETA_Message"] != "":
                message = message + str(request.form["T_ETA_Message"])
            #login = session['username']
            #password = str(session["password"])
            sendemail(from_addr, to_addr, subject, message)
        elif "ETA_check" in key:
            Bug_id = str(request.form[key])
            to_addr = str(request.form[Bug_id]) + "@vmware.com"
            subject = "Please Check the bug:{}".format(Bug_id)
            
            message = ETA_DEFAULT_MESSAGE.format(Bug_id, Bug_id)
            if request.form["ETA_Message"] != "":
                message = message + str(request.form["ETA_Message"])
            
            #login = session['username']
            #password = str(session["password"])
            sendemail(from_addr, to_addr, subject, message)
        elif "W_U_check"in key:
            Bug_id = str(request.form[key])
            to_addr = str(request.form[Bug_id]) + "@vmware.com"
            subject = "Please Check the bug:{}".format(Bug_id)
            
            message = W_U_DEFAULT_MESSAGE.format(Bug_id, Bug_id)
            if request.form["W_U_Message"] != "":
                message = message + str(request.form["W_U_Message"])
            #print message
            #login = session['username']
            #password = str(session["password"])
            sendemail(from_addr, to_addr, subject, message)
    
    
    return render_template('admin_custom.html', message="Finish Processing Email at {}".format(datetime.now().strftime(FMT_YMDHMS)))


def milestone_check(product, version):
    
    
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    cursor=conn.cursor()
    
    sql = """
        select phases.name, eta, weight 
        from milestone, phases 
        where milestone.phase_id in 
        (select id from phases where version_id = {}) 
        and milestone.phase_id = phases.id
        ORDER by eta desc
    """.format(version)
    #print sql
    cursor.execute(sql)
    
    columns = [column[0] for column in cursor.description]
    results = []
    for row in cursor.fetchall():
        results.append(dict(zip(columns, row)))
    cursor.close()
    
    """
    Since the datetime in database is too precise, we have to remove the HMS message
    """
    for key in results:
        if key["eta"] == "null":
            continue
        key["eta"] = key["eta"].date()
    
    #print results
    
    return results



def format_sql(input_string):
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
                
#def sendemail(from_addr, to_addr_list, cc_addr_list, 
def sendemail(from_addr, to_addr,
        subject, message, SMTP_SERVER='smtp.vmware.com'):
    """
    This function helps users sending mail to vmware mail system
    
    This is a critical bug in this system.
    Since the new outlook vmware mail system send mails without authentication, 
    users are able to send email with any source mail address, even if the mail address is upapplicable
    For example, you could send email from a@vmware.com.
    """
    import smtplib
    header  = 'From: {}\n'.format(str(from_addr))
    header += 'To: {}\n'.format(str(to_addr))
    header += 'Subject: {}\n\n'.format(str(subject))
    message = header + message + str(datetime.now())

    
    server = smtplib.SMTP(SMTP_SERVER)
    #server.login(login, password)
    server.sendmail(from_addr, to_addr, message)
    server.quit()
    

@app.route('/autocomplete_profile',methods=['GET'])
def autocomplete_profile():
    import json
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    
    
    results = []
    cursor = conn.cursor()
    
    if "@:" in request.args.get('term'):
        term = str(request.args.get('term')).replace("@:","")
    else:
        term = str(request.args.get('term'))
    
    sql = """SELECT alias_name from custom_alias
    where userid = {}
    and alias_name like "%{}%"
    """.format(session["userid"], term)
    cursor.execute(sql)
    while True:
        record = cursor.fetchone()
        if not record:
            break
        results.append(record[0])
    
    sql = """SELECT login_name from profiles 
        where login_name like "%{}%" or
        realname like "%{}%"
        LIMIT 10""".format(term,term)
        
    cursor.execute(sql)
    while True:
        record = cursor.fetchone()
        if not record:
            break
        results.append(record[0])
    
    """
    Use to process cite-in
    """
    if "@:" in request.args.get('term'):
        temp=[]
        for key in results:
            temp.append("@:"+key)
        results=temp
    return json.dumps(results)

@app.route('/autocomplete_product',methods=['GET'])
def autocomplete_product():
    import json
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    
    sql = """SELECT name from products 
        where name like "{}%"
        LIMIT 10""".format(request.args.get('term'))
    cursor = conn.cursor()
    cursor.execute(sql)
    results = []
    while True:
        record = cursor.fetchone()
        if not record:
            break
        results.append(record[0])
    
    return json.dumps(results)

@app.route('/autocomplete_version',methods=['GET'])
def autocomplete_version():
    import json
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    """
    The order of the query data is followed desc version id
    """
    sql = """SELECT name from versions 
        where product_id = (select id from products where name = '{}')
        and name like "{}%" 
        ORDER by id desc
        LIMIT 10""".format(request.args.get('product'), request.args.get('term'))

    cursor = conn.cursor()
    cursor.execute(sql)
    results = []
    while True:
        record = cursor.fetchone()
        if not record:
            break
        results.append(record[0])
    
    return json.dumps(results)

@app.route('/autocomplete_phase',methods=['GET'])
def autocomplete_phase():
    import json
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    
    sql = """SELECT name from phases 
        where version_id = (select id from versions where name = '{}')
        and name like "{}%"
        LIMIT 10""".format(request.args.get('version'), request.args.get('term'))
    cursor = conn.cursor()
    cursor.execute(sql)
    results = []
    while True:
        record = cursor.fetchone()
        if not record:
            break
        results.append(record[0])
    
    return json.dumps(results)


"""
This function turns the id into full data format in BAR.py
The input of this function is ID-list, and the output will be BID_Record
It only contains bugs and fix_by.
If someone wants to implement longdescs in the future, it could cite or refer to Check_ID in BAR.py
"""
def id_to_full_data(ID_list):
    
    """
    This part handles the detail of bugs
    """
    sql="""
    select {} from bugs
    where bug_id in ({})
    """.format(
    ",".join(["bugs.{}".format(field) for field in gRecordSchema["bugs"]._fields]),
    ",".join(map(str, ID_list))
    )
    
    try:
        global bzdb_conn
        cursor = bzdb_conn.cursor()
        cursor.execute(sql)
    except (AttributeError, MySQLdb.OperationalError):
        logging.warning("Bugzilla Database Reconnect")
        bzdb_conn = MySQLdb.connect(host=BUGZILLA_DATABASE_HOST, port=BUGZILLA_DATABASE_PORT, user=BUGZILLA_DATABASE_USER, passwd=BUGZILLA_DATABASE_PW, db=BUGZILLA_DATABASE_DATABASE)
        cursor = bzdb_conn.cursor()
        cursor.execute(sql)
        
    columns = [column[0] for column in cursor.description]
    Bugs_results = {}
    for row in cursor.fetchall():
        bug = dict(zip(columns, row))
        Bugs_results[bug["bug_id"]] = bug
    
    """
    This part handles the detail of fix_by
    """
    sql = """SELECT {} FROM bug_fix_by_map
             WHERE bug_id in ({})""".format(
            ",".join(["bug_fix_by_map.{}".format(field) for field in gRecordSchema["bug_fix_by_map"]._fields]),
            ",".join(map(str, ID_list)))    
    
    
    
    cursor.execute(sql)
    columns = [column[0] for column in cursor.description]
    Fix_by_results = {}
    for row in cursor.fetchall():
        bug = dict(zip(columns, row))
        Fix_by_results[bug["bug_id"]] = bug

    """
    Change dictionary name
    id -> fix_by_id
    bug_id -> bug_id
    product_id -> fix_by_product_id
    version_id -> fix_by_version_id
    phase_id -> fix_by_phase_id
    """
    local_cursor = local_conn.cursor()
    for idkey in Fix_by_results.keys():
        entry = Fix_by_results[idkey]
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
    
    
    Total_results = {}
    
    for idkey in ID_list:
        Total_results[idkey] = Original_SQL_data_to_BID_Record(bugs = [Bugs_results[idkey]], fix_by = [Fix_by_results[idkey]], conn = bzdb_conn)
    Rule = Option()
    for key in Total_results.keys():
        Urgent_Test(Total_results[key], Rule, bzdb_conn, from_web_ui = True)
        
        
    cursor.close()
    local_cursor.close()
    return Total_results






"""
The idea of cascading autocomplete function can be referenced via
http://stackoverflow.com/questions/2727859/jquery-autocomplete-using-extraparams-to-pass-additional-get-variables
"""
def bug_fix_by_SQL(sql, cursor):
    """
    This is a small function helping me to retrieve the data from local database
    The taret is to process the bug_fix_by_map
    """
    print sql
    cursor.execute(sql)
    bug_fix_by_results={}
    fix_by = cursor.fetchall()
    for key in fix_by:
        bug_id = key[0]
        fix_by_product = key[1]
        fix_by_version = key[2]
        fix_by_phase = key[3]
        """
        In order to print a new line in html column, when there are several bug_fix_by_results within the identical ID, the value should be added sith a newline
        """
        temp_fix_dic = {}
        if fix_by_product == 'Unknown':
            temp_fix_dic = {'product':"",'version':"",'phase':""}
        else:
            if fix_by_version == 'Unknown':
                temp_fix_dic = {'product':fix_by_product,'version':"",'phase':""}
            else:
                if fix_by_phase == 'Unknown':
                    temp_fix_dic = {'product':fix_by_product,'version':fix_by_version,'phase':""}
                else:
                    temp_fix_dic = {'product':fix_by_product,'version':fix_by_version,'phase':fix_by_phase}
        if bug_id not in bug_fix_by_results.keys():
            bug_fix_by_results[bug_id]=[]
        bug_fix_by_results[bug_id].append(temp_fix_dic)
    return bug_fix_by_results

@app.route('/Admin_Custom_List', methods=['GET', 'POST'])
def Admin_Custom_List():
    """
    This function handles the admin_custom_list.html
    This function shows the table of admin_list, and provides administrator a place to edit the admin list
    
    Important!!!!
    This function would probably cause race condition since we modified the document via fopen
    """
    if request.method == 'GET':
        admin_path = open(BAR_ADMINFILE,"r")
        admin_read = []
        for line in admin_path:
            admin_read.append(line.strip())
        admin_ori = ",".join(admin_read)
        admin_path.close()
        return render_template('admin_custom_list.html', admin_list=admin_read, admin_ori=admin_ori)
    elif request.method == 'POST':
        
        str_temp = str(request.form["admin_list_add"]).rstrip(',').split(",")
        add_list = []
        for key in str_temp:
            add_list.append(key.strip())
            
        str_temp = str(request.form["admin_list_remove"]).rstrip(',').split(",")
        remove_list = []
        for key in str_temp:
            remove_list.append(key.strip())
        
        str_temp = str(request.form["admin_list_ori"]).split(",")
        ori_list=[]
        for key in str_temp:
            ori_list.append(key.strip())
        for key in add_list:
            if key not in ori_list:
                ori_list.append(key)
        for key in remove_list:
            if key in ori_list:
                ori_list.remove(key)
        final_result = ori_list[:]
        admin_path = open(BAR_ADMINFILE,"w")
        for key in final_result:
            admin_path.write("{}\n".format(key))
        admin_path.close()
        
        admin_ori = ",".join(final_result)
        admin_list_add = str(request.form["admin_list_add"]).rstrip(',').split(",")
        admin_list_remove = str(request.form["admin_list_remove"]).rstrip(',').split(",")
        return render_template('admin_custom_list.html', admin_list_add=admin_list_add, admin_list_remove=admin_list_remove, admin_list=final_result, admin_ori=admin_ori, message = "Finish List Editing at {}".format(datetime.now().strftime(FMT_YMDHMS)))

def initialize_logger(output_dir):
    """
    This function helps to trigger logger
    In order to log too much garbage message in flask, the message level is lifted into warning
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
     
    # create console handler and set level to info
    handler = logging.StreamHandler()
    #handler.setLevel(logging.INFO)
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
 
    # create debug file handler and set level to debug
    handler = logging.FileHandler(os.path.join(output_dir, "query_and_logging.log"),"a")
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(levelname)s - %(asctime)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    """
    https://docs.python.org/2/howto/logging-cookbook.html
    """
if __name__ == '__main__':
    #logging.basicConfig(filename='query_and_logging.log',level=logging.DEBUG,format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    #logging.basicConfig(level=logging.DEBUG,format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    initialize_logger(os.getcwd())
    logging.warning("Python Server is Initiated")
    #if not app.run(host='triagerobot.eng.vmware.com', debug=True):
    if not app.run(host="0.0.0.0", debug=True):
        logging.warning("Python Server is Terminated")
