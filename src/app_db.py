from google.appengine.ext import db

class UrlStat(db.Model):
    url = db.URLProperty()
    time = db.DateProperty(auto_now_add=True)
    click_count = db.IntegerProperty()
    total_count = db.IntegerProperty()
    comment_count = db.IntegerProperty()
    like_count = db.IntegerProperty()
    share_count = db.IntegerProperty()