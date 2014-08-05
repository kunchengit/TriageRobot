"""
This python file defines the format of custom setting
It could also use to save something else.
If you want to modify the name of variable in self.data, remember to modify database too, since this class is interacted with local database.
"""
class Custom_Setting:
    def __init__(self, userid,
                email_notification=7, 
                query_assignee="",
                query_product="",
                query_version="",
                query_phase="",
                care_member=""):
        #self.respondlist=""
        self.data={}
        self.data["userid"]=int(userid)
        self.data["email_notification"]=int(email_notification)
        self.data["query_assignee"]=query_assignee
        self.data["query_product"]=query_product
        self.data["query_version"]=query_version
        self.data["query_phase"]=query_phase
        self.data["care_member"]=care_member
