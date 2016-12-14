#!/usr/bin/env python

import json
import requests
from NetflixRoulette import *

print "Is movie on Netlix, AMX, Hulu, or Hbo streaming...?"
moviequery = raw_input('Movie search: ') #gb wants triple encoded
print "Web stream sources (if any):"

##NetflixRoulette movie search
try:
   get_netflix_id(moviequery)
   print "netflix"
except Exception:
   pass #sys.exc_clear()

##guidebox movie search
apikey = 'yh7JUQD5rcNN9VVzjp6ovcTna1581H' #temp dev key
#go here for new dev key: https://api.guidebox.com/production-key
region = 'US'
baseapiurl = 'http://api-public.guidebox.com/v1.43/%s/%s' % (region, apikey)
moviesearchurl = '%s/search/movie/title/%s/exact' % (baseapiurl, moviequery)
r = requests.get(moviesearchurl)
moviesearch = json.loads(r.text)
id = moviesearch["results"][0]["id"]

##guidebox get movie info
movieinfourl = '%s/movie/%s' % (baseapiurl, id)
r = requests.get(movieinfourl)
movieinfo = json.loads(r.text)
 
##guidebox print avail web stream sources
for websource in movieinfo["subscription_web_sources"]:
   print websource["source"]

#import requests_cache
#todo: add flask front end
#todo: prettyprint of some sort for debugging

#todo: make/use virtual env and use py3
# sudo apt-get install python3
# pip install --user virtualenv
# # Create the directory for this workshop
# $ mkdir flask-workshop
# $ cd flask-workshop
# # Create a Python 3 virtualenv under the 'flaskenv' directory
# $ virtualenv --python=python3 flaskenv
# # Activate the virtual environment
# $ source flaskenv/bin/activate

#def main():