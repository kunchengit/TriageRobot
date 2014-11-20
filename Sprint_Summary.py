import os
import re
import urllib
import cookielib
import xmlrpclib, httplib, sys
from urlparse import urljoin

import mechanize
from bs4 import BeautifulSoup

#report_order = ['triaged', 'fixed']
#report_order = ['triaged','fixed', 'no_checkin_request', 'no_checkin']

class Sprint_Summary:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.names = ['Debugging', 'sprint-ready', 'Sprint-Accepted', 'Fixed']
        self.summary_items = dict()
        self.summary_items['Debugging'] = {'params_func':self.debugging_params}
        self.summary_items['sprint-ready'] = {'params_func':self.sprint_ready_params}
        self.summary_items['Sprint-Accepted'] = {'params_func':self.sprint_accepted_params}
        self.summary_items['Fixed'] = {'params_func':self.fixed_params}

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

    def get_data(self, options, name):
        params = self.summary_items[name]['params_func'](options)
        
        br = self.get_logined_browser()
        data = urllib.urlencode(params)

        print data

        post_url = '''https://bugzilla.eng.vmware.com/buglist.cgi'''
        page = br.open(post_url,data)

        try:
            print name
            result = self.page_to_dict(page)
        except:
            result = dict()
            result['head'] = ['']
            result['data'] = ['']
        #result['params'] = data
        #result['name'] = report_name
        #result['description'] = self.report_item[report_name]['desc_func'](options)
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
        print len(data)
        return len(data)

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
        params = self.read_default_params('fixed_sprint_all.txt')
        assigned_to = options['assigned_to']
        params.append(('email1', assigned_to))

        params.append(('chfieldto', options['date_end']))
        
        for fix_by_product_name in options['fix_by_product_name']:
            params.append(('fix_by_product_name', fix_by_product_name))

        for fix_by_version_name in options['fix_by_version_name']:
            params.append(('fix_by_version_name', fix_by_version_name))

        for fix_by_phase_name in options['fix_by_phase_name']:
            params.append(('fix_by_phase_name', fix_by_phase_name))

        return params

    def debugging_params(self, options):
        params = self.read_default_params('debugging.txt')
        assigned_to = options['assigned_to']
        params.append(('email1', assigned_to))
        params.append(('chfieldto', options['date_end']))

        for fix_by_product_name in options['fix_by_product_name']:
            params.append(('fix_by_product_name', fix_by_product_name))

        for fix_by_version_name in options['fix_by_version_name']:
            params.append(('fix_by_version_name', fix_by_version_name))

        for fix_by_phase_name in options['fix_by_phase_name']:
            params.append(('fix_by_phase_name', fix_by_phase_name))

        return params

    def sprint_ready_params(self, options):
        params = self.read_default_params('sprint_ready.txt')
        assigned_to = options['assigned_to']
        params.append(('email1', assigned_to))
        params.append(('chfieldto', options['date_end']))

        for fix_by_product_name in options['fix_by_product_name']:
            params.append(('fix_by_product_name', fix_by_product_name))

        for fix_by_version_name in options['fix_by_version_name']:
            params.append(('fix_by_version_name', fix_by_version_name))

        for fix_by_phase_name in options['fix_by_phase_name']:
            params.append(('fix_by_phase_name', fix_by_phase_name))

        return params

    def sprint_accepted_params(self, options):
        params = self.read_default_params('sprint_accepted_all.txt')
        assigned_to = options['assigned_to']
        params.append(('email1', assigned_to))
        params.append(('chfieldto', options['date_end']))

        for fix_by_product_name in options['fix_by_product_name']:
            params.append(('fix_by_product_name', fix_by_product_name))

        for fix_by_version_name in options['fix_by_version_name']:
            params.append(('fix_by_version_name', fix_by_version_name))

        for fix_by_phase_name in options['fix_by_phase_name']:
            params.append(('fix_by_phase_name', fix_by_phase_name))

        return params
