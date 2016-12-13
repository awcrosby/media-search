#!/usr/bin/env python

import requests
#import requests_cache
import json

#def main():

temp_apikey = 'yh7JUQD5rcNN9VVzjp6ovcTna1581H'

##enter movie query
moviequery =  'clueless' #need to triple encode this

##perform movie search
apikey = temp_apikey
region = 'US'
baseapiurl = 'http://api-public.guidebox.com/v1.43/%s/%s' % (region, apikey)
moviesearchurl = '%s/search/movie/title/%s/exact' % (baseapiurl, moviequery)
#r = requests.get(moviesearchurl)
#moviesearch = json.loads(r.text)

#print "title: ", moviesearch["results"][0]["title"]
#print "id: ", moviesearch["results"][0]["id"]
id = 42929

##get movie info
movieinfourl = '%s/movie/%s' % (baseapiurl, id)
print movieinfourl
r = requests.get(movieinfourl)
movieinfo = json.loads(r.text)
#print "subscription_web_sources: ", movieinfo["subscription_web_sources"]
 
##print stream links and show as yes/no
for websource in movieinfo["subscription_web_sources"]:
   #if websource[0]["source"] = "hulu_plus": print "Hulu Plus supported"
   #if websource[0]["source"] = "hbo_now": print "HBO supported"
   print websource["source"]
   
##todo check all sub sources in py and print them out to see which ones to look for or ignore... like amazon prime ones that are not pure prime: https://api.guidebox.com/apidocs
##todo find way to ignore non sub things, and print out all you find
##todo - maybe add caching, add to flask so can enter form



