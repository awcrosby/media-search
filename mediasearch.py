#!/usr/bin/env python
import json
import requests
from NetflixRoulette import *
import guidebox

def mediasearch(query, qtype):
    #do search via guidebox, note: query='Terminator2', results: exact=0, fuzzy=1... use fuzzy and take first result
    guidebox.api_key = json.loads(open('apikeys.json').read())["guidebox_prod_apikey"]
    movies = guidebox.Search.movies(precision='fuzzy', field='title', query=query)

    f = open( 'movies.txt', 'w' )
    f.write( 'exact search, and results were > 0, query = ' + query + '\n dict = ' + repr(movies) + '\n' )
    f.close()

    gbid = movies['results'][0]['id']
    media = guidebox.Movie.retrieve(id=gbid)  #dive deeper into api to find sources

    #for websource in media['subscription_web_sources']:
    #    sources.append(websource['source'])
    #dont think we do this: if exact search has a result continue, else fuzzy and display "did you mean..."

    #on link click continue
    #pull movie info via guidebox, populate sources
    #search netflixroulette with gb title

    #==================================================
    sources = []
    try:  #NetflixRoulette search
        get_netflix_id(query)  #returns error if cannot find it netflix's library
        sources.append('Netflix')
    except Exception:
        pass #sys.exc_clear()

    try:  #guidebox apiv2 search
        guidebox.api_key = json.loads(open('apikeys.json').read())["guidebox_prod_apikey"]
        if (qtype == 'movie'):
            movies = guidebox.Search.movies(field='title', query=query)
            gbid = movies['results'][0]['id']
            media = guidebox.Movie.retrieve(id=gbid)  #dive deeper into api to find sources
        elif (qtype == 'show'):
            media = 'temp'
        for websource in media['subscription_web_sources']:
            sources.append(websource['source'])
    except Exception:
        pass
    
    return sources

if __name__ == "__main__":
    print "Check if movie is on Netlix, AMZ, Hulu, or HBO."
    moviequery = raw_input('Movie search: ')
    print "Web stream sources (if any):"
    results = mediasearch(moviequery)
    print results
    
#import requests_cache
#todo: add flask front end
#todo: prettyprint or some sort for debugging

#def main():
