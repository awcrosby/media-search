#!/usr/bin/env python
from flask import Flask, render_template, request, redirect, url_for
import json
import guidebox
import time
import requests
import re
import time
app = Flask(__name__)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q')  # or if POST: query = request.form['q']

    # type param comes from either button display name or 'did you mean' links
    qtype = 'show' if 'show' in request.args.get('type').lower() else 'movie'

    if not query:  # exit early if query is blank
        return render_template('index.html')

    guidebox.api_key = json.loads(open('apikeys.json').read())['guidebox']
    sources = {}
    src, epcount, seasons = ([], {}, {})
    source_sub, source_free, source_tvp = ([], [], [])

    # if movie perform movie search
    if qtype == 'movie':
        medias = guidebox.Search.movies(precision='fuzzy',
                                        field='title', query=query)
        if not (medias['total_results'] > 0):  # exit early if no results
            return render_template('index.html', isresult=0,
                                   query=query, qtype=qtype)
        gbid = medias['results'][0]['id']  # take first result
        media = guidebox.Movie.retrieve(id=gbid)  # more info on movie

        for ws in media['subscription_web_sources']:
            y = {'name': ws['source'],
                 'display_name': ws['display_name'],
                 'link': ws['link'],
                 'type': 'subscription'}
            sources[ws['source']] = y
            src.append(y)

        # set media info to send to template
        med = {'title': media['title'],
               'year': media['release_year'],
               'imdb': media['imdb'],
               'img': media['poster_120x171']}

    # if show then perform show search across all episodes
    elif qtype == 'show':
        start = time.time()
        medias = guidebox.Search.shows(precision='fuzzy', field='title',
                                       query=query)
        if not (medias['total_results'] > 0):  # exit early if no results
            return render_template('index.html', isresult=0,
                                   query=query, qtype=qtype)
        gbid = medias['results'][0]['id']  # take first result

        # get all episodes in 1 or 2 api requests, to reduce api wait time
        media = guidebox.Show.episodes(id=gbid, limit=1)
        results = media['total_results']
        if results <= 200:
            media = guidebox.Show.episodes(id=gbid, include_links=True,
                                           limit=results)
        else:
            media = guidebox.Show.episodes(id=gbid, include_links=True,
                                           limit=200)
            m2 = guidebox.Show.episodes(id=gbid, include_links=True,
                                        limit=200, offset=200)
            media['results'] += m2['results']
        api_time = time.time()
        print 'api request time: ', api_time - start

        # iterate all episodes, add source types: sub, free, tv_provider
        for ep in media['results']:
            if ep['season_number'] == 0:  # skips season 0 tv specials
                continue

            source_types = ['subscription_web_sources',
                            'free_web_sources',
                            'tv_everywhere_web_sources']
            for source_type in source_types:
                for s in ep[source_type]:
                    if not any(d.get('name', None) == s['source'] for d in src):
                        newsource = {'name': s['source'],
                                     'display_name': s['display_name'],
                                     'link': s['link'],
                                     'type': source_type,
                                     'seasons': list((ep['season_number'], ))}  # 1-tuple TODO remove
                        src.append(newsource)
                        seasons[s['source']] = []
                    # create or update epcount, append season to list if not there
                    epcount[s['source']] = epcount.get(s['source'],0) + 1
                    if ep['season_number'] not in seasons[s['source']]:
                        seasons[s['source']].append(ep['season_number'])
        print 'episode proc time: ', time.time() - api_time

        # for each source, set episode count and seasons
        for s in src:
            s['epcount'] = epcount[s['name']]  # set the source dict epcount
            s['seasons'] = seasons[s['name']]  # set the source dict seasons 
            s['seasons'].sort()  # sort the seasons

            # convert seasons to string so template can display
            strseasons = list()  #TODO see if can use list already in dict here
            for x in s['seasons']:
                strseasons.append(str(x))

            # if seasons are contiguous, then make into a range
            x, end = (0, 0)
            lst = strseasons
            for y in range(1, len(lst)-x):
                if int(lst[x]) + y == int(lst[x+y]):
                    end = y
            if end:  # if first entry has subsequent contiguous
                lst[x] = lst[x] + '-' + lst[end]
                for z in range(x+1, end+1):
                    del lst[x+1]

            s['seasons'] = list(strseasons)  # overwrite w/ str list

        # set media info to send to template
        m = medias['results'][0]
        med = {'title': m['title'], 'year': m['first_aired'][:4],
               'imdb': m['imdb_id'], 'img': m['artwork_208x117']}

    # delete redundant hbo/showtime sources, and sources that don't work
    for k in sources.keys():  #TODO update this
        if sources[k]['name'] in ['hbo_amazon_prime',
                                  'showtime_amazon_prime',
                                  'hulu_with_showtime',
                                  'showtime',  # tv_provider
                                  'hbo',  # tv_provider
                                  'directv_free',
                                  'comedycentral_tveverywhere',
                                  'fox_tveverywhere']:
            del sources[k]

    # split sources into separate lists
    for s in src:
        if s['type'] == 'subscription_web_sources':
            source_sub.append(s)
        elif s['type'] == 'free_web_sources':
            source_free.append(s)
        elif s['type'] == 'tv_everywhere_web_sources':
            source_tvp.append(s)

    # build other_results to send to template
    other_results = []
    for m in medias['results'][1:]:
        x = {'href': 'search?q=' + m['title'] + '&type=' + qtype,
             'title': m['title']}
        if (m['wikipedia_id'] != 0) and (m['wikipedia_id'] is not None):
            other_results.append(x)  # keep if not very obscure

    # temp debugging
    f = open('medias.txt', 'w')
    f.write('query = ' + query + '\n dict = ' + repr(medias) + '\n')
    f.close()
    f = open('singlemedia.txt', 'w')
    f.write('dict = ' + repr(media) + '\n')
    f.close()

    return render_template('index.html', sources=src, media=med,
                           query=query, qtype=qtype,
                           other_results=other_results[:4], isresult=1,
                           source_sub=source_sub, source_free=source_free,
                           source_tvp=source_tvp)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8181)
