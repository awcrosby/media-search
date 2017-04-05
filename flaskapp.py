#!/usr/bin/env python
from flask import Flask, render_template, request, redirect, url_for
import json
import guidebox
app = Flask(__name__)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q')  # or if POST: query = request.form['q']
    if not query:  # exit early if query is blank
        return render_template('index.html')
    guidebox.api_key = json.loads(open('apikeys.json').read())["guidebox"]
    sources = []

    qtype = 'movie'  # temp hardcode query type
    if qtype == 'movie':  # note: q='Terminator2' results exact=0 fuzzy=1
        medias = guidebox.Search.movies(precision='fuzzy', field='title', query=query)
        if not (medias['total_results'] > 0):  # exit early if no search results
            return render_template('index.html', isresult=0, query=query, qtype=qtype)
        gbid = medias['results'][0]['id']  # take first result
        media = guidebox.Movie.retrieve(id=gbid)  # more info on movie

        for websource in media['subscription_web_sources']:
            x = {'name': websource['source'], 'link': websource['link']}
            sources.append(x)
        med = {'title': media['title'], 'year': media['release_year'], 'imdb': media['imdb']}
    elif qtype == 'show':
        medias = guidebox.Search.shows(precision='fuzzy', field='title', query=query)
        if not (medias['total_results'] > 0):  # exit early if no search results
            return render_template('index.html', isresult=0, query=query, qtype=qtype)
        gbid = medias['results'][0]['id']  # take first result
        media = guidebox.Show.available_content(id=gbid)  # more info on show

        #media = guidebox.Show.retrieve(id=gbid)  # get more info on movie
        #f = open('singlemedia.txt', 'w')
        #f.write('dict = ' + repr(media) + '\n')
        #f.close()

        for allsource in media['results']['web']['episodes']['all_sources']:
            if allsource['type'] == 'subscription':
                x = {'name': allsource['source'], 'link': 'none'}
                sources.append(x)
        m = medias['results'][0]
        med = {'title': m['title'], 'year': m['first_aired'][:4], 'imdb': m['imdb_id']}

    # alter display name of sources and limit what is displayed
    mapping = {'netflix': 'Netflix',
               'hbo_now': 'HBO (and Amazon + HBO)',
               'hulu_plus': 'Hulu',
               'amazon_prime': 'Amazon Prime',
               'showtime_subscription': 'Showtime (and Amazon/Hulu + Showtime)'}
    for source in sources:
        if source['name'] in mapping.keys():
            source['name'] = mapping[source['name']]
        else:
            # sources.remove(source)
            source['name'] = '~' + source['name']

    # build other results to send to template
    other_results = []
    for m in medias['results'][1:]:
        x = {'href': 'search?q=' + str(m['title']), 'title': str(m['title'])}
        if(m['wikipedia_id'] != 0):  # filters out the very obscure
            other_results.append(x)

    # temp debugging
    f = open('medias.txt', 'w')
    f.write('query = ' + query + '\n dict = ' + repr(medias) + '\n')
    f.close()
    f = open('singlemedia.txt', 'w')
    f.write('dict = ' + repr(media) + '\n')
    f.close()

    return render_template('index.html', sources=sources, media=med,
                           query=query, qtype=qtype,
                           other_results=other_results[:4], isresult=1)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8181)
