#!/usr/bin/env python
from flask import Flask, render_template, request, redirect
import json, guidebox
from NetflixRoulette import *
app = Flask(__name__)
results = []

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/result', methods = ['POST'])
def displayresults():
    query = request.form['movieq']
    qtype = 'movie'

    #do search via guidebox, note: query='Terminator2', results: exact=0, fuzzy=1... use fuzzy and take first result
    guidebox.api_key = json.loads(open('apikeys.json').read())["guidebox_prod_apikey"]
    movies = guidebox.Search.movies(precision='fuzzy', field='title', query=query)
    gbid = movies['results'][0]['id']
    media = guidebox.Movie.retrieve(id=gbid)  #dive deeper into api to find sources

    #find sources in guidebox, if found then check netflixroulette
    sources = []
    for websource in media['subscription_web_sources']:
        sources.append(websource['source'])
    if movies['total_results'] > 0:
        try:
            get_netflix_id(media['title'])  #returns error if not found in netflix library
            sources.insert(0, 'Netflix')
        except Exception:
            pass #sys.exc_clear()
    
    #build header and footer to send to template
    footer = ''
    if sources:
        other_results = [] #check if other results and add to footer
        for movie in movies['results'][1:]:
            other_results.append(movie['title'])
        if other_results:
            footer = '...or did you mean?: '
            for other in other_results[:3]: footer += other + ', '
            footer = footer[:-2]

    f = open( 'movies.txt', 'w' )
    f.write( 'query = ' + query + '\n dict = ' + repr(movies) + '\n' )
    f.close()

    f = open( 'singlemovie.txt', 'w' )
    f.write( 'dict = ' + repr(media) + '\n' )
    f.close()
    
    return render_template('index.html', sources=sources, footer=footer, media=media, query=query, qtype=qtype, other_results=other_results)

if __name__ == "__main__":
  app.run(host='0.0.0.0', port=8181)
