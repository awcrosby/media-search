#!/usr/bin/env python
from flask import Flask, render_template, request, redirect, url_for
import json
import guidebox
import time
app = Flask(__name__)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q')  # or if POST: query = request.form['q']
    qtype = 'movie'  # set default value if not included
    qtype = request.args.get('type')
    if not query:  # exit early if query is blank
        return render_template('index.html')
    guidebox.api_key = json.loads(open('apikeys.json').read())["guidebox"]
    sources = {}

    if qtype == 'movie':  # note: q='Terminator2' results exact=0 fuzzy=1
        medias = guidebox.Search.movies(precision='fuzzy', field='title', query=query)
        if not (medias['total_results'] > 0):  # exit early if no search results
            return render_template('index.html', isresult=0, query=query, qtype=qtype)
        gbid = medias['results'][0]['id']  # take first result
        media = guidebox.Movie.retrieve(id=gbid)  # more info on movie

        for websource in media['subscription_web_sources']:
            x = {'name': websource['source'], 'link': websource['link']}
            sources[websource['source']] = x
        med = {'title': media['title'], 'year': media['release_year'],
               'imdb': media['imdb']}
    elif qtype == 'show':
        medias = guidebox.Search.shows(precision='fuzzy', field='title', query=query)
        if not (medias['total_results'] > 0):  # exit early if no search results
            return render_template('index.html', isresult=0, query=query, qtype=qtype)
        gbid = medias['results'][0]['id']  # take first result
        media = guidebox.Show.episodes(id=gbid, include_links=True, limit=200)
        
        seasons = []
        for x in media['results']:  # go thru every episode and add source
            #for websource in x['subscription_web_sources']:
            #    y = {'name': websource['source'], 'link': websource['link']}
            #    sources[websource['source']] = y
            #if x['season_number'] not in seasons:
            #    seasons.append(x['season_number'])
            
            for websource in x['subscription_web_sources']:
                if websource['source'] not in sources: # make new source entry
                    y = {'name': websource['source'],
                         'link': websource['link'],
                         'epcount': 1,
                         'seasons': set(str(x['season_number']))}
                    sources[websource['source']] = y
                else:  # increase epcount and ensure season is accounted for
                    sources[websource['source']]['epcount'] += 1
                    sources[websource['source']]['seasons'].add(str(x['season_number']))
                    

        print "resultcount = ", len(media['results'])
        for x in sources:
            print "source = " + sources[x]['name']
            print "epcount = ", sources[x]['epcount']
            print "seasons = ", sources[x]['seasons']
        #source: name, link, ep, season[]
        #sources['netflix'] = name:netflix, link:..., ep:#, season:[] 

        #media = guidebox.Show.available_content(id=gbid)  # non-episode method
        #for allsource in media['results']['web']['episodes']['all_sources']:
        #    if allsource['type'] == 'subscription':
        #        x = {'name': allsource['source'], 'link': 'none'}
        #        sources.append(x)

        m = medias['results'][0]
        med = {'title': m['title'], 'year': m['first_aired'][:4],
               'imdb': m['imdb_id']}

    # alter display name of sources and limit what is displayed
    mapping = {'netflix': 'Netflix',
               'hbo_now': 'HBO (and Amazon + HBO)',
               'hulu_plus': 'Hulu',
               'amazon_prime': 'Amazon Prime',
               'showtime_subscription': 'Showtime (and Amazon/Hulu + Showtime)'}
    for s in sources:
        if sources[s]['name'] in mapping.keys():
            sources[s]['name'] = mapping[sources[s]['name']]
        else:
            # sources.remove(source)
            sources[s]['name'] = '~' + sources[s]['name']

    # build other results to send to template
    other_results = []
    for m in medias['results'][1:]:
        x = {'href': 'search?mq=' + str(m['title']), 'title': str(m['title'])}
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
