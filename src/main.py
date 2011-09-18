from __future__ import division

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db
from google.appengine.api import memcache

import app_db
import datetime
import time

import webappfb
import logging
from django.utils import simplejson

import os
from google.appengine.ext.webapp import template
"""
{'search': {'pattern': 'search.*', 'query': "SELECT url, normalized_url, share_count, like_count, comment_count, total_count, click_count FROM link_stat WHERE url = '{squery}'"}, 
'link_stats': {'pattern': 'links.*', 'query': 'SELECT url, share_count, like_count, comment_count, total_count, click_count FROM link_stat WHERE url IN ( SELECT url FROM link WHERE owner = {*user*} )'}, 
'user_stats': {'pattern': 'links.*', 'query': 'SELECT link_id, owner, owner_comment, created_time, title, summary, url, image_urls FROM link WHERE owner = {*user*}'}}
"""

SEARCH_URL = "SELECT url, normalized_url, share_count, like_count, comment_count, total_count, click_count FROM link_stat WHERE url IN ('{URL}')"

class URLStat:
    def __init__(self,url,):
        pass


class StatsRenderer(webappfb.FacebookCanvasHandler):
    def render_stats(self, stats, links):
        # stats = link view statistics
        # links = user links
        self.response.out.write("Rendering...")
        link_info = {}
        temp_stats = {}
        
        # Stats:
        # 0 = URL
        # 1 = Share Count
        # 2 = Like count
        # 3 = Comment Count
        # 4 = Total count
        # 5 = Click Count
        
        # Links:
        # 0 = link_id
        # 1 = owner
        # 2 = owner_comment
        # 3 = created_time
        # 4 = title
        # 5 = summary
        # 6 = url
        # 7 = image_urls
        
        for s in stats: temp_stats[s[0]] = s
        
        for i in links:
            url = i[6]
            if not url: continue
            link_info[url] = {'info':i,
                               'stats':temp_stats[url]}
        
        #for link in links:
        #    pass
        
        path = os.path.join(os.path.dirname(__file__), 'templates/render_results.html')
        self.response.out.write(template.render(path,{'links':link_info}))  
        
        
class MainPage(StatsRenderer):
    def canvas(self):
        if not self.facebook.check_session(self.request):
            self.redirect(self.facebook.get_login_url(next=[self.request.path,""][self.request.path == '/']))
            return
        else:
            stats = memcache.get("%s_stats"%self.facebook.uid)
            links = memcache.get("%s_links"%self.facebook.uid)
            if stats and links:
                self.redirect("http://apps.facebook.com/link_stats/")
                return
            
            self.response.out.write("NOT CACHED!")
            try:
                #raise Exception
                t1 = time.time()
                stats = simplejson.loads(self.request.get("fb_sig_link_stats"))
                links = simplejson.loads(self.request.get("fb_sig_user_stats"))
                logging.info("Simplejson taken %s"%str(time.time()-t1))
            except Exception,e:
                self.response.out.write("Error, could not get your link stats! Please refresh")
                return
            memcache.set("%s_stats"%self.facebook.uid,stats,time=240)
            memcache.set("%s_links"%self.facebook.uid,links,time=240)
            self.response.out.write("Done!")
            self.render_stats(stats,links)
            
class RedirectPage(StatsRenderer):
    def canvas(self):
        stats = memcache.get("%s_stats"%self.facebook.uid)
        links = memcache.get("%s_links"%self.facebook.uid)
        if not links or not stats:
            self.redirect("http://apps.facebook.com/link_stats/links")
            return
        self.response.out.write("CACHED!")
        self.render_stats(stats,links)
            
class SearchPage(webappfb.FacebookCanvasHandler):
    def canvas(self):
        if not self.facebook.check_session(self.request):
            self.redirect(self.facebook.get_login_url(next=[self.request.path,""][self.request.path == '/']))
            return
        else:
            #logging.info("------ DEBUG ------")
            #for i in self.request.arguments():
            #    logging.info("%s = %s"%(i,self.request.get(i)))
            #logging.info("-------------------")
            if not self.request.get("squery"):
                self.response.out.write("No query entered!")
                path = os.path.join(os.path.dirname(__file__), 'templates/search_default.html')
                self.response.out.write(template.render(path,None))
                return
            
            #query = ""
            #for i in """!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""
            
            if self.request.get("fb_sig_data_preloading_errors"):
                logging.error("FQL preload error: %s"%self.request.get("fb_sig_data_preloading_errors"))
                self.response.out.write("There was an error processing your request - try refreshing!")
                return
            results = []
            if self.request.get("fb_sig_search"):
                t_results = simplejson.loads(self.request.get("fb_sig_search"))
                for r in t_results:
                    t = {}
                    t['click_count'] = r[6]
                    t['total_count'] = r[5]
                    t['comment_count'] = r[4]
                    t['like_count'] = r[3]
                    t['share_count'] = r[2]
                    t['normalized_url'] = r[1]
                    if not r[0].startswith("http://") or r[0].startswith("https://"):
                        t['url'] = "http://"+r[0]
                    else:
                        t['url'] = r[0]
                    results.append(t)
            else:
                logging.error("No results in preload - fetching ourselves...")
                for i in xrange(5):
                    try:
                        results = self.facebook.fql.query(SEARCH_URL.replace("{URL}",self.request.get("squery")))
                    except Exception,e:
                        logging.error("FQL error %s"%e)
                        continue            
            
            if results:
                results = results[0]
            
            use_chart = False
                        
            # For the chart
            try:
                stat_items = ['click_count','comment_count','like_count','share_count']
                chart = {}
                highest_value = max([ results[k] for k in stat_items ])
                logging.info("Highest value: %s"%highest_value)
                for x in stat_items:
                    chart[x] = results[x]
                for x in chart:
                    chart[x] = int(round((chart[x] / highest_value) * 100))
                use_chart = True
            except Exception,e:
                import traceback
                traceback.print_exc()
                logging.error("Chart rendering exception: %s"%e)
            
            template_values = {'results':results,
                               'query':self.request.get('squery'),
                               'chart':chart,
                               'use_chart':use_chart
                               }
            
            path = os.path.join(os.path.dirname(__file__), 'templates/search.html')
            self.response.out.write(template.render(path, template_values))
            
            if results['share_count'] == 0:
                return
            
            if memcache.get("db_"+results['url']):
                return
            try:
                r = app_db.UrlStat.all().filter("url = ",results['url']).filter("time = ",datetime.date.today()).fetch(1)
            except Exception,e:
                logging.error("Datastore get error: %s"%e)
                return
            if r: 
                return
            try:
                app_db.UrlStat(
                       url=results['url'],
                       click_count=results['click_count'],
                       total_count=results['total_count'],
                       comment_count=results['comment_count'],
                       like_count=results['like_count'],
                       share_count=results['share_count']
                       ).put()
            except:
                logging.error("Datastore put error: %s"%e)
                return
            memcache.set("db_"+results['url'],1,time=400)
            
            #db.run_in_transaction(self.add_stat,results)

        
        

application = webapp.WSGIApplication([('/links', MainPage),
                                      ('/',RedirectPage),
                                      ('/search',SearchPage)], debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
