#!/usr/bin/env python
from flask import Flask, render_template, request, redirect, url_for
import json, guidebox
app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search', methods = ['GET'])
def search():
    query = request.args.get('q')  #or if POST: query = request.form['q']
    qtype = 'movie'  #temp hardcode query type
    if not query:  #exit early if query is blank
        return render_template('index.html')
    
    #guidebox fuzzy search take 1st result, note: q='Terminator2' results exact=0 fuzzy=1
    guidebox.api_key = json.loads(open('apikeys.json').read())["guidebox_prod_apikey"]
    movies = guidebox.Search.movies(precision='fuzzy', field='title', query=query)
    isresult = movies['total_results'] > 0
    if not isresult:  #exit early if no search results
        return render_template('index.html', isresult=isresult, query=query, qtype=qtype)
    gbid = movies['results'][0]['id']
    media = guidebox.Movie.retrieve(id=gbid)  #dive deeper into api to find sources

    #find sources in guidebox
    sources = []
    for websource in media['subscription_web_sources']:
        x = {'name': websource['source'], 'link': websource['link']}
        sources.append(x)
    
    #alter display name of sources and limit what is displayed    
    mapping = {'netflix': 'Netflix',
               'hbo_now': 'HBO (and Amazon + HBO)',
               'hulu_plus': 'Hulu',
               'amazon_prime': 'Amazon Prime',
               'showtime_subscription': 'Showtime (and Amazon/Hulu + Showtime)'
              }
    for source in sources:
        if source['name'] in mapping.keys():
            source['name'] = mapping[source['name']]
        else:
            #sources.remove(source)
            source['name'] = '~' + source['name']
    
    #build other results to send to template
    other_results = []
    for movie in movies['results'][1:]:
        x = {'href': 'search?q=' + str(movie['title']), 'title': str(movie['title'])}
        if( movie['wikipedia_id'] != 0):  #filters out the very obscure
            other_results.append(x)

    #temp debugging
    f = open( 'movies.txt', 'w' )
    f.write( 'query = ' + query + '\n dict = ' + repr(movies) + '\n' )
    f.close()
    f = open( 'singlemovie.txt', 'w' )
    f.write( 'dict = ' + repr(media) + '\n' )
    f.close()
   
    return render_template('index.html', sources=sources, media=media, query=query, qtype=qtype, other_results=other_results[:4], isresult=isresult)

if __name__ == "__main__":
  app.run(host='0.0.0.0', port=8181)
