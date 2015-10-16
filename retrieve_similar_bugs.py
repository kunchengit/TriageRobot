import MySQLdb
import pandas
import itertools
import numpy as np
import bm25fe
import pickle
import subprocess
import jsd
from gensim import corpora
from gensim import matutils
from gensim.models import ldamulticore
import getpass
import os

def retrieve_similar_bugs(query_list, length_list, dictionary_address, topicmodel_address, rankmodel_address):
    
    print 0, getpass.getuser(), os.getcwd()

    conn = MySQLdb.connect(host='10.117.8.41', port=3306, user='root', passwd='vmware', db='bugfeature')
    cur = conn.cursor()

    print 1, getpass.getuser(), os.getcwd()
    
    sql = '''SELECT * FROM bugs_cpdplatform_ff'''
    bugs = pandas.io.sql.read_sql(sql, conn)
    
    print 2, getpass.getuser(), os.getcwd()

    dictionary = corpora.Dictionary.load_from_text(dictionary_address)
    topicmodel = ldamulticore.LdaMulticore.load(topicmodel_address)

    print 3, getpass.getuser(), os.getcwd()
    
    num_terms = len(dictionary)
    bugs['text'] = (bugs['short_desc'] +' '+ bugs['long_desc']).map(lambda x: dictionary.doc2bow(x.split()))
    bugs['engineer'] = (bugs['assigned_to'].map(str)+' '+bugs['needinfo']).map(lambda x: x.split())
    bugs.loc[:,'short_desc'] = bugs['short_desc'].map(lambda x: matutils.corpus2dense([dictionary.doc2bow(x.split())], num_terms, 1)[:,0])
    bugs.loc[:,'long_desc'] = bugs['long_desc'].map(lambda x: matutils.corpus2dense([dictionary.doc2bow(x.split())], num_terms, 1)[:,0])
    
    appearance = np.array(list(bugs['text'].map(lambda x: matutils.corpus2dense([x], num_terms, 1)[:,0]>0)))
    df = appearance.sum(0)
    idf = np.log(bugs.shape[0]/df)
    avgfl = np.array([np.array(list(bugs['short_desc'])).sum(1).mean(), np.array(list(bugs['long_desc'])).sum(1).mean()])

    bugs = bugs.set_index(['bug_id'])

    print 4, getpass.getuser(), os.getcwd()
    
    bm = bm25fe.bm25fe(K1=1.2, d_B=(0.75, 0.75), d_W = (2, 1), K3=1.2, q_B=(0.75, 0.75), q_W=(2, 1))

    results = {}
    lines = []
    for item in query_list:
        item = int(item)
        bugs['score'] = bugs.apply(lambda x: bm.score(idf, avgfl, [x[13], x[14]],[bugs.loc[item,'short_desc'], bugs.loc[item,'long_desc']]), axis = 1)
        bugs_sorted = bugs.sort(['score'], ascending = False).iloc[:100].reset_index()
        
        results[item] = bugs_sorted.loc[:,['bug_id']]
        # print results[item]
        
        # idx = 0
        # lines = []
        for idx in xrange(100):
            sim_title = bugs_sorted.iloc[idx]['short_desc'][bugs.loc[item,'short_desc']>0].sum()/max(bugs_sorted.iloc[idx]['short_desc'].sum(), 1)
            score = bugs_sorted.iloc[idx]['score']
            # cluster = topicmodel.inference([bugs_sorted.iloc[idx]['text'], bugs.loc[item['query'],'text']])
            cluster = topicmodel.inference([bugs_sorted.iloc[idx]['text'], bugs.loc[item,'text']])[0]
            dis_topic = jsd.JSD(cluster[0], cluster[1])
            sim_hos = False
            if (bugs_sorted.iloc[idx]['host_op_sys'] == bugs.loc[item,'host_op_sys']) and (bugs_sorted.iloc[idx]['host_op_sys'] != 'Unknown'):
                sim_hos = True
            sim_gos = False
            if (bugs_sorted.iloc[idx]['guest_op_sys'] == bugs.loc[item,'guest_op_sys']) and (bugs_sorted.iloc[idx]['guest_op_sys'] != 'Unknown'):
                sim_gos = True
            sim_pd = False
            if (bugs_sorted.iloc[idx]['product_id'] == bugs.loc[item,'product_id']):
                sim_pd = True
            sim_cg = False
            if (bugs_sorted.iloc[idx]['category_id'] == bugs.loc[item,'category_id']):
                sim_cg = True
            sim_cp = False
            if (bugs_sorted.iloc[idx]['component_id'] == bugs.loc[item,'component_id']):
                sim_cp = True
            sim_pr = False
            if (bugs_sorted.iloc[idx]['priority'] == bugs.loc[item,'priority']):
                sim_pr = True
            sim_fi_pd = False
            if (bugs_sorted.iloc[idx]['found_in_product_id'] == bugs.loc[item,'found_in_product_id']) and (bugs_sorted.iloc[idx]['found_in_product_id'] != 0):
                sim_fi_pd = True
            sim_fi_ver = False
            if (bugs_sorted.iloc[idx]['found_in_version_id'] == bugs.loc[item,'found_in_version_id']) and (bugs_sorted.iloc[idx]['found_in_version_id'] != 0):
                sim_fi_ver = True
            sim_fi_ph = False
            if (bugs_sorted.iloc[idx]['found_in_phase_id'] == bugs.loc[item,'found_in_phase_id']) and (bugs_sorted.iloc[idx]['found_in_phase_id'] != 0):
                sim_fi_ph = True
    
            if (bugs_sorted.iloc[idx]['cf_security'] == bugs.loc[item,'cf_security']) and (bugs_sorted.iloc[idx]['cf_security'] ==1):
                sim_security = 2
            elif (bugs_sorted.iloc[idx]['cf_security'] == bugs.loc[item,'cf_security']) and (bugs_sorted.iloc[idx]['cf_security'] ==0):
                sim_security = 1
            else:
                sim_security = 0
        
            sim_engineer = False
            if (len(set(bugs_sorted.iloc[idx]['engineer']) & set(bugs.loc[item,'engineer'])) >0):
                sim_engineer = True
        
            lines.append(str(0)+' qid:'+str(item)+' 1:'+str(sim_title)+' 2:'+str(score)+' 3:'+str(dis_topic)+' 4:'+str(int(sim_hos))+' 5:'+str(int(sim_gos))+' 6:'+str(int(sim_pd))+' 7:'+str(int(sim_cg))+' 8:'+str(int(sim_cp))+' 9:'+str(int(sim_pr))+' 10:'+str(int(sim_fi_pd))+' 11:'+str(int(sim_fi_ver))+' 12:'+str(int(sim_fi_ph))+' 13:'+str(sim_security)+' 14:'+str(int(sim_engineer))+' # '+str(bugs_sorted.iloc[idx]['bug_id'])+'\n')

    print 5, getpass.getuser(), os.getcwd()

    f = open('/home/TriageRobot/query.txt', 'w')
    f.writelines(lines)
    f.close()
            
    subprocess.call(('java', '-jar', '/root/chenkun/Duplicate-bugs-retrieval/RankLib-2.1-patched.jar', '-load', rankmodel_address, '-rank', '/home/TriageRobot/query.txt', '-score', '/home/TriageRobot/score.txt'))
    # subprocess.call(('java', '-jar', 'RankLib-2.1-patched.jar', '-load', 'AdaRank.txt', '-rank', 'query.txt', '-score', 'score.txt'))
    # subprocess.call(('java', '-jar', 'RankLib-2.1-patched.jar', '-load', 'RankNet.txt', '-rank', 'query.txt', '-score', 'score.txt'))
    
    score_rank = []
    qid = -1
    f = open('/home/TriageRobot/score.txt', 'r')
    for line in f:
        if int(line.split()[0]) != qid:
            if score_rank:
                results[qid]['score_rank'] = score_rank
                score_rank = []
            qid = int(line.split()[0])
            score_rank.append(float(line.split()[2]))
        else:
            score_rank.append(float(line.split()[2]))
    results[qid]['score_rank'] = score_rank
    f.close()
    
    # print results
    idx = 0
    for key in results:
        bugs_ranked = results[key].sort(['score_rank'], ascending = False).set_index(['bug_id'])
    
        ranklist = []
        i = 0
        while len(ranklist) < int(length_list[idx]):
            # print bugs_ranked.iloc[i]['bug_id']
            if bugs_ranked.index[i] != key:
                child = False
                for j in xrange(len(ranklist)):
                    if bugs.loc[bugs_ranked.index[i],'summary'] == bugs.loc[ranklist[j],'summary']:
                        # if len(set([bugs_ranked.index[i]]) & set(item['rel'])) > 0:
                        #     ranklist[j] = bugs_ranked.index[i]
                        child = True
                        break
                if not child:
                    ranklist.append(bugs_ranked.index[i])
            # ranklist.append(bugs_ranked.index[i])
            i += 1
        results[key] = ranklist
        idx += 1
    
    return results




def find_bug():
    f = open('/home/TriageRobot/query.txt', 'w')
