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
    qtype = request.args.get('type')
    if (qtype != 'movie') & (qtype != 'show'):
        qtype = 'movie'  # set default value if not included
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

        for ws in media['subscription_web_sources']:
            x = {'name': ws['source'], 'link': ws['link']}
            sources[ws['source']] = x
        med = {'title': media['title'],  # create to send to template
               'year': media['release_year'],
               'imdb': media['imdb'],
               'img': media['poster_120x171']}
    elif qtype == 'show':
        medias = guidebox.Search.shows(precision='fuzzy', field='title', query=query)
        if not (medias['total_results'] > 0):  # exit early if no search results
            return render_template('index.html', isresult=0, query=query, qtype=qtype)
        gbid = medias['results'][0]['id']  # take first result
        media = guidebox.Show.episodes(id=gbid, include_links=True, limit=250)

        for x in media['results']:  # go thru every episode and add source
            for ws in x['subscription_web_sources']:
                if ws['source'] not in sources:  # make new source entry
                    y = {'name': ws['source'],
                         'link': ws['link'],
                         'epcount': 1,
                         'seasons': list(str(x['season_number']))}
                    sources[ws['source']] = y
                else:  # increase epcount and ensure season is accounted for
                    sources[ws['source']]['epcount'] += 1
                    if str(x['season_number']) not in sources[ws['source']]['seasons']:
                        sources[ws['source']]['seasons'].append(str(x['season_number']))
                sources[ws['source']]['seasons'].sort()

        m = medias['results'][0]
        med = {'title': m['title'], 'year': m['first_aired'][:4],
               'imdb': m['imdb_id'], 'img': m['artwork_208x117']}

    # alter display name of sources and limit what is displayed
    mapping = {'netflix': 'Netflix',
               'hbo_now': 'HBO (and Amazon + HBO)',
               'hulu_plus': 'Hulu',
               'amazon_prime': 'Amazon Prime',
               'showtime_subscription': 'Showtime (and Amazon/Hulu + Showtime)'}
    for k in sources.keys():
        if k in mapping.keys():
            sources[k]['name'] = mapping[k]
        else:
            del sources[k]

    # build other results to send to template
    other_results = []
    for m in medias['results'][1:]:
        x = {'href': 'search?q=' + m['title'] + '&type=' + qtype,
             'title': m['title']}
        if (m['wikipedia_id'] != 0) & (m['wikipedia_id'] is not None):
            other_results.append(x)  # filters out the very obscure

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
