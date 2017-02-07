#!/usr/bin/env python
import json
import requests
from NetflixRoulette import *

def mediasearch( moviequery ):
    results = ""
    ##NetflixRoulette movie search
    try:
        get_netflix_id(moviequery)
        results += "netflix"
    except Exception:
        pass #sys.exc_clear()

    ##guidebox movie search
    apis = json.loads(open('apikeys.json').read())
    gbkey = apis["guidebox_prod_apikey"]
    region = 'US'
    baseapiurl = 'http://api-public.guidebox.com/v1.43/%s/%s' % (region, gbkey)
    moviesearchurl = '%s/search/movie/title/%s/exact' % (baseapiurl, moviequery) #gb wants triple encoded
    r = requests.get(moviesearchurl)
    moviesearch = json.loads(r.text)
    try:
        id = moviesearch["results"][0]["id"] #fix traceback on q=darko
        ##guidebox get movie info
        movieurl = '%s/movie/%s' % (baseapiurl, id)
        r = requests.get(movieurl)
        movieinfo = json.loads(r.text)
        
        ##guidebox avail stream sources
        for websource in movieinfo["subscription_web_sources"]:
            results += websource["source"]
    except Exception:
        pass #sys.exc_clear()
    
    return results

if __name__ == "__main__":
    print "Check if movie is on Netlix, AMZ, Hulu, or HBO."
    moviequery = raw_input('Movie search: ')
    print "Web stream sources (if any):"
    results = mediasearch(moviequery)
    print results
    
#import requests_cache
#todo: add flask front end
#todo: prettyprint or some sort for debugging

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