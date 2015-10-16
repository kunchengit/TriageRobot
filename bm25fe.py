import numpy as np

class bm25fe():
    """Implements the BM25FE scoring algorithm.
    """
 
    def __init__(self, K1=1.2, d_B=(0.75, 0.75), d_W = (1, 1), K3=1.2, q_B=(0.75, 0.75), q_W=(1, 1)):
        """
        
        :param B: free parameter, see the BM25 literature. Keyword arguments of
            the form ``fieldname_B`` (for example, ``body_B``) set field-
            specific values for B.
        :param K1: free parameter, see the BM25 literature.
        """
        
        self.K1 = K1
        self.d_B = d_B
        self.d_W = d_W
        
        self.K3 = K3
        self.q_B = q_B
        self.q_W = q_W
        
        self.fields = len(d_B)
        
        
    def score(self, idf, avgfl, doc, query):
        
        idf = np.array(idf)
        avgfl = np.array(avgfl)
        doc = np.array(doc)
        query = np.array(query)
        
        doc_n = np.zeros(doc[0].size)
        query_n = np.zeros(query[0].size)
        for i in xrange(self.fields):
            doc_n += self.d_W[i]/(1-self.d_B[i]+self.d_B[i]*doc[i].sum()/avgfl[i])*doc[i]
            query_n += self.q_W[i]/(1-self.q_B[i]+self.q_B[i]*query[i].sum()/avgfl[i])*query[i]
        
        return (idf*(self.K1+1)*doc_n/(self.K1+doc_n)*(self.K3+1)*query_n/(self.K3+query_n)).sum()
    
    
    def derivative(self, idf, avgfl, doc, query):
        
        idf = np.array(idf)
        avgfl = np.array(avgfl)
        doc = np.array(doc)
        query = np.array(query)
        
        doc_n = np.zeros(doc[0].size)
        query_n = np.zeros(query[0].size)
        for i in xrange(self.fields):
            doc_n += self.d_W[i]/(1-self.d_B[i]+self.d_B[i]*doc[i].sum()/avgfl[i])*doc[i]
            query_n += self.q_W[i]/(1-self.q_B[i]+self.q_B[i]*query[i].sum()/avgfl[i])*query[i]
        
        der =[]
        
        der.append((idf*doc_n*(doc_n-1)/((self.K1+doc_n)**2)*(self.K3+1)*query_n/(self.K3+query_n)).sum())
        
        for i in xrange(self.fields):
            der.append((idf*self.K1*(self.K1+1)/((self.K1+doc_n)**2)*self.d_W[i]*(1-doc[i].sum()/avgfl[i])/((1-self.d_B[i]+self.d_B[i]*doc[i].sum()/avgfl[i])**2)*doc[i]*(self.K3+1)*query_n/(self.K3+query_n)).sum())
            
        for i in xrange(self.fields):
            der.append((idf*self.K1*(self.K1+1)/((self.K1+doc_n)**2)/(1-self.d_B[i]+self.d_B[i]*doc[i].sum()/avgfl[i])*doc[i]*(self.K3+1)*query_n/(self.K3+query_n)).sum())
        
        
        der.append((idf*(self.K1+1)*doc_n/(self.K1+doc_n)*query_n*(query_n-1)/((self.K3+query_n)**2)).sum())
        
        for i in xrange(self.fields):
            der.append((idf*(self.K1+1)*doc_n/(self.K1+doc_n)*self.K3*(self.K3+1)/((self.K3+query_n)**2)*self.q_W[i]*(1-query[i].sum()/avgfl[i])/((1-self.q_B[i]+self.q_B[i]*query[i].sum()/avgfl[i])**2)*query[i]).sum())
            
        for i in xrange(self.fields):
            der.append((idf*(self.K1+1)*doc_n/(self.K1+doc_n)*self.K3*(self.K3+1)/((self.K3+query_n)**2)/(1-self.q_B[i]+self.q_B[i]*query[i].sum()/avgfl[i])*query[i]).sum())
        
        return np.array(der)