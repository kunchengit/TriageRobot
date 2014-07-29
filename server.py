"""
Need to implement following commands
pip install flask
pip install django
pip install MySQLdb
"""

from Bugzilla_webservice import *
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
#LOCAL_DATABASE_PORT
LOCAL_DATABASE_USER = "root"
LOCAL_DATABASE_PW = "vmware"
LOCAL_DATABASE_DATABASE = "TriageRobot"

app = Flask(__name__)
app.secret_key = 'B1Z298g/3y2 R~lHHbjaN]LWX/,?RT'
cache = SimpleCache(default_timeout=300)
BUGZILLA_URL = 'https://bugzilla.eng.vmware.com/xmlrpc.cgi'
BAR_OPTION_DIRECTORY = "BAR_option/"

BAR_OFILENAME = BAR_OPTION_DIRECTORY + "option.p"
BAR_ADMINFILE = BAR_OPTION_DIRECTORY + "admin.p"

with app.test_request_context('/hello', method='POST'):
    # now you can do something with the request until the
    # end of the with block, such as basic assertions:
    assert request.path == '/hello'
    assert request.method == 'POST'


@app.route('/')
def index():
    return render_template('query.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
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
    
    return render_template('query.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    This function helps user to log out.
    All the session will be left
    """
    logging.warning("{} logout successfully.".format(session['username']))
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('admin', None)
    flash('You were logged out')
    return redirect(url_for('query'))



@app.route('/entries_processing', methods = ['GET', 'POST'])
def entries_processing():
    """
    This function handles entries_processing.html
    It shows the queried table
    This function also provides the function of add/remove keywords and add comments
    """
    
    cookie_file = cache.get('cookie')
    print cookie_file
    if cookie_file is None:
        session['logged_in'] = False
        return redirect(url_for('query'))
    server = BugzillaServer(BUGZILLA_URL, cookie_file)
    result={}
    selection={}
    if request.form["A_R_Selection"]=="A":
        selection["A_R_Selection"] = "Add"
        selection_flag = True
    else:
        selection["A_R_Selection"] = "Remove"
        selection_flag = False
    
    """
    Add/Remove keywords and commends
    THe result dictionary is also built in this itinerary
    """
    
    for key in request.form.keys():
        print key
        if "check_id_" in key: 
            """
            since the there are lots of other keys will be transmited with request.form
            Therefore, I set a "if" to retrieve bug_id value
            """
            check_id = int(key.replace("check_id_",""))
            try:
                result[check_id]["keywords"] = str(request.form["keywords"])
            except:
                result[check_id]={}
                result[check_id]["bug_id"] = check_id
                result[check_id]["keywords"] = str(request.form["keywords"])
            if selection_flag:
                logging.warning("{} add keywords:({}) to {}.".format(session['username'], str(request.form["keywords"]), str(request.form[key])))
                server.add_keywords(request.form[key], *str(request.form["keywords"]).split(","))
            else:
                logging.warning("{} remove keywords:({}) to {}.".format(session['username'], str(request.form["keywords"]), check_id))
                server.remove_keywords(request.form[key], *str(request.form["keywords"]).split(","))

        if "comment_id_" in key:
            comment_id = int(key.replace("comment_id_",""))
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
    print results
    return render_template('entries_processing.html', bugs=results, selection=selection)

@app.route('/query', methods=['GET', 'POST'])
def query():
    error = None
    return render_template('query.html')

@app.route('/show_entries', methods=['GET', 'POST'])
def show_entries():
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
    
    assigned_to = request.form['assigned_to'].rstrip(',')
    """
    request.form["assigned_to"] processing finish
    """
    
    
    if request.method == 'POST':
        conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
        if not conn:
            flash("Fail to Connect my Sql, please try again later")
            return render_template('query.html', error="Fail to Connect MySQL, Please try again later")
        Input_Rule = assigned_to+request.form['fix_by_product']+request.form['fix_by_version']+request.form['product']
        
        logging.warning("{} queries for assigned_to:{}\t fix_by_product:{}\t fix_by_version:{}\t product:{}.".format(session['username'], assigned_to, request.form['fix_by_product'], request.form['fix_by_version'], request.form['product']))
        
        check_sum = hashlib.md5(Input_Rule).hexdigest()
        sql = """select md5 from rules where md5 = '{}'""".format(check_sum)
        
        cursor = conn.cursor()
        cursor.execute(sql)
        
        result = cursor.fetchone()
        
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
            return render_template('query.html', error="The profile name is unfindable. \n Please corrent your spelling")
        
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
            
            if str(request.form['fix_by_version']) != "" and len_db < len_input:
                logging.warning("{} queries are not approved since the version name is unfindable.".format(session['username']))
                return render_template('query.html', error="The version name is unfindable. \n Please corrent your spelling")
        else:
            fix_by_version_number = "fix_by_version_id"
            
        """
        Change the product number to "fix_by_product_id"
        """
        if str(request.form['fix_by_product']) == "":
            fix_by_product_number = "fix_by_product_id"
        
        
        
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
        if not result: #This is a new rule
            o_filename = BAR_OFILENAME;
            filename = BAR_OPTION_DIRECTORY+check_sum+".p";
            command = "python BAR.py";
            Format_Rule=assigned_to+":"+request.form['fix_by_product']+":"+request.form['fix_by_version']+":"+request.form['product']+"::\n"
            fp = open(filename, 'w')
            fp.write(Format_Rule)
            fp.close()
            fp = open(o_filename, 'a')
            fp.write(Format_Rule)
            fp.close()
            os.system(command + " --option " + filename + " --wo_update_information")
            os.system("rm " + filename)
        
        """
        This should be modified to match the database
        """
        conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
        
        
        
        people = "','".join(assigned_to.split(','))
            
        sql = """SELECT * from bugs 
        where assigned_to in ({}) 
        ORDER by highlighted_by DESC, weight DESC, bug_id""".format(
        profile_number)
        
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [column[0] for column in cursor.description]
        impure_results = []
        for row in cursor.fetchall():
            impure_results.append(dict(zip(columns, row)))
            
        sql = """select bug_id, fix_by_product_rn, fix_by_version_rn from bug_fix_by_map
        where bug_id in ({})
        and fix_by_product_id in ({})
        and fix_by_version_id in ({})
        order by bug_id""".format(",".join(str(k["bug_id"]) for k in impure_results),
        fix_by_product_number,
        fix_by_version_number)
        
        bug_fix_by_results = Bug_Fix_By_SQL(sql, cursor)
        
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
        """
        sql = """
        select bug_when from bugs_activity where who in ({}) and bug_when>'{}' and fieldid = 12 and added = 'triage-accepted'
        """.format(profile_number, date.today() - relativedelta(months = 6) + relativedelta(day=1))
        
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
        
        
        
        
    return render_template('show_entries.html', bugs = Pure_results, fix_by=bug_fix_by_results, triage_date = date_results, assigned = assigned_to)

@app.route('/Admin_Custom_Webpage', methods=['GET', 'POST'])
def Admin_Custom_Webpage():
    """
    This function is a intro webpage, and this function handles admin_custom_webpage.html
    """
    return render_template('admin_custom.html')

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
            
    sql = """select bug_id, fix_by_product_rn, fix_by_version_rn from bug_fix_by_map
        where bug_id in ({})
        order by bug_id""".format(",".join(str(k["bug_id"]) for k in T_ETA_bug_results))
    T_ETA_bug_fix_by_results = Bug_Fix_By_SQL(sql, cursor)
    
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
            
    sql = """select bug_id, fix_by_product_rn, fix_by_version_rn from bug_fix_by_map
        where bug_id in ({})
        order by bug_id""".format(",".join(str(k["bug_id"]) for k in ETA_bug_results))
    
    ETA_bug_fix_by_results = Bug_Fix_By_SQL(sql, cursor)
    
    
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
    
    sql = """select bug_id, fix_by_product_rn, fix_by_version_rn from bug_fix_by_map
        where bug_id in ({})
        order by bug_id""".format(",".join(str(k["bug_id"]) for k in W_U_bug_results))
    W_U_bug_fix_by_results = Bug_Fix_By_SQL(sql, cursor)
        
    return render_template('admin_custom_email.html', 
    T_ETA_bug_results = T_ETA_bug_results, 
    T_ETA_bug_fix_by_results = T_ETA_bug_fix_by_results, 
    ETA_bug_results = ETA_bug_results, 
    ETA_bug_fix_by_results = ETA_bug_fix_by_results,
    W_U_bug_results = W_U_bug_results,
    W_U_bug_fix_by_results = W_U_bug_fix_by_results)

@app.route('/Admin_Email_Processing', methods=['GET', 'POST'])
def Admin_Email_Processing():
    """
    This function handles the post action of admin_custom_email.html.
    This function will send email to the correspond assignee with correspond comments
    The name of the variables in this function should be identical to the namr of the variables in Admin_Custom_Email
    """
    print request.form.keys()
    from_addr = session["username"] + "@vmware.com"
    
    for key in request.form.keys():
        if "T_ETA_check" in key:
            Bug_id = str(request.form[key])
            to_addr = str(request.form[Bug_id]) + "@vmware.com"
            subject = "Please Check the bug:{}".format(Bug_id)
            message = """
                Please Check the bug:{}
                This bug is need to set a ETA after Triage-accepted
                https://bugzilla.eng.vmware.com/show_bug.cgi?id={}
                """.format(Bug_id, Bug_id)
            #login = session['username']
            #password = str(session["password"])
            sendemail(from_addr, to_addr, subject, message)
        elif "ETA_check" in key:
            Bug_id = str(request.form[key])
            to_addr = str(request.form[Bug_id]) + "@vmware.com"
            subject = "Please Check the bug:{}".format(Bug_id)
            message = """
                Please Check the bug:{}
                This bug is already expired
                https://bugzilla.eng.vmware.com/show_bug.cgi?id={}
                """.format(Bug_id, Bug_id)
            #login = session['username']
            #password = str(session["password"])
            sendemail(from_addr, to_addr, subject, message)
        elif "W_U_check"in key:
            Bug_id = str(request.form[key])
            to_addr = str(request.form[Bug_id]) + "@vmware.com"
            subject = "Please Check the bug:{}".format(Bug_id)
            message = """
                Please Check the bug:{}
                This bug is not updated for a long time
                https://bugzilla.eng.vmware.com/show_bug.cgi?id={}
                """.format(Bug_id, Bug_id)
            #print message
            #login = session['username']
            #password = str(session["password"])
            sendemail(from_addr, to_addr, subject, message)
    
    
    return render_template('admin_custom.html')
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
    print message
    
    server = smtplib.SMTP(SMTP_SERVER)
    #server.login(login, password)
    server.sendmail(from_addr, to_addr, message)
    server.quit()
    

@app.route('/autocomplete_profile',methods=['GET'])
def autocomplete_profile():
    import json
    conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
    
    sql = """SELECT login_name from profiles 
        where login_name like "%{}%" or
        realname like "%{}%"
        LIMIT 10""".format(request.args.get('term'), request.args.get('term'))
        
    cursor = conn.cursor()
    cursor.execute(sql)
    results = []
    while True:
        record = cursor.fetchone()
        if not record:
            break
        results.append(record[0])
    
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
    print "version"
    sql = """SELECT name from versions 
        where product_id = (select id from products where name = '{}')
        and name like "{}%"
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
"""
The idea of cascading autocomplete function can be referenced via
http://stackoverflow.com/questions/2727859/jquery-autocomplete-using-extraparams-to-pass-additional-get-variables
"""
def Bug_Fix_By_SQL(sql, cursor):
    """
    This is a small function helping me to retrieve the data from local database
    The taret is to process the bug_fix_by_map
    """
    cursor.execute(sql)
    bug_fix_by_results={}
    fix_by = cursor.fetchall()
    for key in fix_by:
        bug_id = key[0]
        fix_by_product = key[1]
        fix_by_version = key[2]
        """
        In order to print a new line in html column, when there are several bug_fix_by_results within the identical ID, the value should be added sith a newline
        """
        if bug_id not in bug_fix_by_results.keys():
            bug_fix_by_results[bug_id]=""
        else:
            bug_fix_by_results[bug_id] += "\n"
        if fix_by_product == 'Unknown':
                bug_fix_by_results[key[0]]=""
        else:
                if fix_by_version == 'Unknown':
                    bug_fix_by_results[bug_id] += fix_by_product
                else:
                    bug_fix_by_results[bug_id] += fix_by_product+"-"+fix_by_version   
    return bug_fix_by_results

@app.route('/Admin_Custom_List', methods=['GET', 'POST'])
def Admin_Custom_List():
    """
    This function handles the admin_custom_list.html
    This function shows the table of admin_list, and provides administrator a place to edit the admin list
    """
    if request.method == 'GET':
        admin_path = open(BAR_ADMINFILE,"r")
        admin_read = []
        for line in admin_path:
            admin_read.append(line.strip())
        admin_list = ",".join(admin_read)
        admin_path.close()
        return render_template('admin_custom_list.html', admin_list=admin_list)
    elif request.method == 'POST':
        print request.form["admin_list_add"]
        print request.form["admin_list_remove"]
        
        str_temp = str(request.form["admin_list_add"]).split(",")
        add_list = []
        for key in str_temp:
            add_list.append(key.strip())
            
        str_temp = str(request.form["admin_list_remove"]).split(",")
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
        
        admin_path = open(BAR_ADMINFILE,"w")
        admin_path.write("\n".join(ori_list))
        admin_path.close()
        
        admin_list = ",".join(ori_list)
        admin_list_add = str(request.form["admin_list_add"])
        admin_list_remove = str(request.form["admin_list_remove"])
        return render_template('admin_custom_list.html', admin_list_add=admin_list_add, admin_list_remove=admin_list_remove, admin_list=admin_list)    

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
    if not app.run(host='10.117.8.249', debug=True):
        logging.warning("Python Server is Terminated")
