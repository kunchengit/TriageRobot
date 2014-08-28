#!/usr/bin/python

import MySQLdb
import sys
import time
import tempfile
import pickle
import logging
import os
import hashlib
from os.path import exists, join
from collections import namedtuple, defaultdict, OrderedDict # Python 2.7

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
 

SCRIPTS_DIR = os.path.abspath(os.path.dirname(__file__))
BAR_OPTION_DIRECTORY = os.path.join(SCRIPTS_DIR, "BAR_option/")
CUSTOM_OPTION_DIRECTORY = os.path.join(SCRIPTS_DIR, "Custom_Setting/")

BAR_OFILENAME = BAR_OPTION_DIRECTORY + "option.p"
BAR_ADMINFILE = BAR_OPTION_DIRECTORY + "admin.p"

LOCAL_DATABASE_HOST = "localhost"
#LOCAL_DATABASE_PORT
LOCAL_DATABASE_USER = "root"
LOCAL_DATABASE_PW = "vmware"
LOCAL_DATABASE_DATABASE = "TriageRobot"

conn = MySQLdb.connect(host=LOCAL_DATABASE_HOST, user=LOCAL_DATABASE_USER, passwd=LOCAL_DATABASE_PW, db=LOCAL_DATABASE_DATABASE)
cursor = conn.cursor()

sql="""
    delete from custom_alias 
    where for_admin = 1
    """
    
cursor.execute(sql)

sql="""
    select profiles.login_name, custom_alias.* from custom_alias
    inner join profiles
    on profiles.userid = custom_alias.userid
    """
cursor.execute(sql)
columns = [column[0] for column in cursor.description]
results = []
for row in cursor.fetchall():
    results.append(dict(zip(columns, row)))
#print results

alias_list = results

admin_path = open(BAR_ADMINFILE,"r")
admin_read = []
for line in admin_path:
    admin_read.append(line.strip())
admin_path.close()

sql="""
    select * from profiles
    where login_name in ('{}')
    """.format("','".join(admin_read))
cursor.execute(sql)
columns = [column[0] for column in cursor.description]
results = []
for row in cursor.fetchall():
    results.append(dict(zip(columns, row)))
#print results

for item in results:
    id = item["userid"]
    print 'item'
    print item
    for orig_record in alias_list:
        if str(orig_record['userid']) != str(id):
            record = orig_record.copy()
            record['userid'] = id
            record['alias_name'] = '_'.join([record['login_name'], 'alias', record['alias_name']])
            record["md5"] = hashlib.md5(record['alias_name'] + str(id)).hexdigest()
            record['for_admin'] = '1'
            del record['login_name']
            sql="""
            INSERT INTO custom_alias ({})
            value ({}) 
            ON DUPLICATE KEY UPDATE
            {}
            """.format(
                ','.join(record.keys()),
                ','.join(map(str,(format_sql(k) for k in record.values()))),
                ','.join('{}={}'.format(k,format_sql(record[k])) for k in record)
            )
            cursor.execute(sql)

cursor.close()
conn.close()

