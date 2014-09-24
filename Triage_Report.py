import os
import re
import urllib
import cookielib
import xmlrpclib, httplib, sys
from urlparse import urljoin

import mechanize
from bs4 import BeautifulSoup

#report_order = ['triaged', 'fixed']
report_order = ['triaged','fixed', 'no_checkin_request', 'no_checkin']

class Triage_Report:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.report_item = dict()
        self.report_item['fixed'] = {'params_func':self.fixed_params, 'desc_func':self.fixed_description}
        self.report_item['triaged'] = {'params_func':self.triaged_params, 'desc_func':self.triaged_description}
        self.report_item['no_checkin_request'] = {'params_func':self.no_checkin_request_params, 'desc_func':self.no_checkin_request_description}
        self.report_item['no_checkin'] = {'params_func':self.no_checkin_params, 'desc_func':self.no_checkin_description}
        self.report_list = report_order
        

    def get_logined_browser(self):
        username = self.username
        password = self.password
        br = mechanize.Browser()

        cj = cookielib.LWPCookieJar()
        br.set_cookiejar(cj)

        br.set_handle_equiv(False)
        br.set_handle_gzip(False)
        br.set_handle_redirect(True)
        br.set_handle_referer(True)
        br.set_handle_robots(False)
        br.set_handle_refresh(mechanize._http.HTTPRefererProcessor(), max_time=1)

        #br.set_debug_http(True)
        #br.set_debug_redirects(True)
        #br.set_debug_responses(True)

        br.set_debug_http(False)
        br.set_debug_redirects(False)
        br.set_debug_responses(False)

        br.addheaders = [('User-agent', 'Mozilla/4.0 (compatible; U; MSIE 6.0; Windows NT 5.1)')]
        #br.set_proxies({'http': 'http://proxy.vmware.com:3128', 'https': 'http://proxy.vmware.com:3128'})

        page = br.open('https://bugzilla.eng.vmware.com/index.cgi')
        #print page.read()
        br.select_form(nr=0)
        br.form.set_all_readonly(False)
        br['Bugzilla_login'] = username
        br['Bugzilla_password'] = password

        r = br.submit()
        res = r.get_data()

        #print res
        return br

    def get_report_data(self, report_name, options):
        params = self.report_item[report_name]['params_func'](options)
        
        br = self.get_logined_browser()
        data = urllib.urlencode(params)

        print data

        post_url = '''https://bugzilla.eng.vmware.com/buglist.cgi'''
        page = br.open(post_url,data)

        try:
            result = self.page_to_dict(page)
        except:
            result = dict()
            result['head'] = ['']
            result['data'] = ['']
        result['params'] = data
        result['name'] = report_name
        result['description'] = self.report_item[report_name]['desc_func'](options)
        return result

    def page_to_dict(self, page):
        result = dict()
        data = list()
        soup = BeautifulSoup(page)
        rows = soup.find("table", id='buglistSorter').find("tbody").find_all("tr")
        for row in rows:
            rowdata = list()
            cells = row.find_all("td")
            for cell in cells:
                rn = cell.get_text() 
                rowdata.append(rn)
            data.append(rowdata)

        head = list()
        row = soup.find("table", id='buglistSorter').find("thead").find("tr")
        cells = row.find_all("th")
        for cell in cells:
            rn = cell.get_text().replace('\n','').strip()
            head.append(rn)
    
        result['head'] = head
        result['data'] = data
        
        return result

    def read_default_params(self, filename):
        file_name = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'Triage_Chart_Query_Template', filename)
        file = open(file_name)
        content = file.read()
        lines = content.splitlines()
        params = list()
        for line in lines:
            if line.strip().startswith('#') or not line:
                continue
            tuple = line.split("=")
            params.append((tuple[0], tuple[1]))
        return params

    def get_report_name_list(self):
        return self.report_list

    def fixed_params(self, options):
        params = self.read_default_params('fixed.txt')
        assigned_to = options['assigned_to']
        params.append(('email1', assigned_to))

        params.append(('chfieldfrom', options['date_begin']))
        params.append(('chfieldto', options['date_end']))
        
        for fix_by_product_name in options['fix_by_product_name']:
            params.append(('fix_by_product_name', fix_by_product_name))

        for fix_by_version_name in options['fix_by_version_name']:
            params.append(('fix_by_version_name', fix_by_version_name))

        for fix_by_phase_name in options['fix_by_phase_name']:
            params.append(('fix_by_phase_name', fix_by_phase_name))

        return params

    def fixed_description(self, options):
        return "Bugs been fixed between %s and %s" %(options['date_begin'], options['date_end'])

    def triaged_params(self, options):
        params = self.read_default_params('triaged.txt')
        assigned_to = options['assigned_to']
        params.append(('email1', assigned_to))

        params.append(('chfieldfrom', options['date_begin']))
        params.append(('chfieldto', options['date_end']))
        
        for fix_by_product_name in options['fix_by_product_name']:
            params.append(('fix_by_product_name', fix_by_product_name))

        for fix_by_version_name in options['fix_by_version_name']:
            params.append(('fix_by_version_name', fix_by_version_name))

        for fix_by_phase_name in options['fix_by_phase_name']:
            params.append(('fix_by_phase_name', fix_by_phase_name))

        return params


    def triaged_description(self, options):
        return "Bugs been triage-accepted between %s and %s" %(options['date_begin'], options['date_end'])

    def no_checkin_request_params(self, options):
        params = self.read_default_params('no_checkin_request.txt')
        assigned_to = options['assigned_to']
        params.append(('email1', assigned_to))

        #no need time frame
        #params.append(('chfieldfrom', options['date_begin']))
        #params.append(('chfieldto', options['date_end']))
        
        for fix_by_product_name in options['fix_by_product_name']:
            params.append(('fix_by_product_name', fix_by_product_name))

        for fix_by_version_name in options['fix_by_version_name']:
            params.append(('fix_by_version_name', fix_by_version_name))

        for fix_by_phase_name in options['fix_by_phase_name']:
            params.append(('fix_by_phase_name', fix_by_phase_name))

        return params

    def no_checkin_request_description(self, options):
        return "Bugs in triage-accepted status, but NO CheckinApprovalRequested filed"

    def no_checkin_params(self, options):
        params = self.read_default_params('no_checkin.txt')
        assigned_to = options['assigned_to']
        params.append(('email1', assigned_to))

        #no need time frame
        #params.append(('chfieldfrom', options['date_begin']))
        #params.append(('chfieldto', options['date_end']))
        
        for fix_by_product_name in options['fix_by_product_name']:
            params.append(('fix_by_product_name', fix_by_product_name))

        for fix_by_version_name in options['fix_by_version_name']:
            params.append(('fix_by_version_name', fix_by_version_name))

        for fix_by_phase_name in options['fix_by_phase_name']:
            params.append(('fix_by_phase_name', fix_by_phase_name))

        return params

    def no_checkin_description(self, options):
        return "Bugs been CheckinApproved, but code haven't been checked in yet"

def test():
    options = dict()
    options['assigned_to'] = 'fangchiw,hillzhao,vaibhavk,shanpeic,nmukuri'
    options['date_begin'] = '2014-09-15'
    options['date_end'] = '2014-09-23'
    options['fix_by_product_name'] = ['vsphere', 'esx']
    options['fix_by_version_name'] = ['5.1 P06', '5.1 P06Ps']
    options['fix_by_phase_name'] = []
    
    tr = Triage_Report('fangchiw', '''we'reno.2''')
    for report_item in tr.get_report_name_list():
        print tr.get_report_data(report_item, options)

#test()
