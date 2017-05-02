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

    # if movie perform movie search
    if qtype == 'movie':
        medias = guidebox.Search.movies(precision='fuzzy',
                                        field='title', query=query)
        if not (medias['total_results'] > 0):  # exit early if no search results
            return render_template('index.html', isresult=0,
                                   query=query, qtype=qtype)
        gbid = medias['results'][0]['id']  # take first result
        media = guidebox.Movie.retrieve(id=gbid)  # more info on movie

        for ws in media['subscription_web_sources']:
            x = {'name': ws['source'], 'link': ws['link']}
            sources[ws['source']] = x
        med = {'title': media['title'],  # create to send to template
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
                                           limit = 200)
            m2 = guidebox.Show.episodes(id=gbid, include_links=True,
                                           limit = 200, offset=200)
            media['results'] += m2['results']
        api_time = time.time()
        print 'api request time: ', api_time - start

        # iterate all episodes, add source types: sub, free, tv_provider
        for x in media['results']:
            if x['season_number'] == 0:  # skips season 0 tv specials
                continue
            for ws in x['subscription_web_sources']:
                if ws['source'] not in sources:  # make new source entry
                    y = {'name': ws['source'],
                         'link': ws['link'],
                         'type': 'subscription',
                         'epcount': 1,
                         'seasons': list((x['season_number'], )) }  #1-tuple
                    sources[ws['source']] = y
                else:  # increase epcount and ensure season is accounted for
                    sources[ws['source']]['epcount'] += 1
                    if x['season_number'] not in sources[ws['source']]['seasons']:
                        sources[ws['source']]['seasons'].append(x['season_number'])
            for ws in x['free_web_sources']:
                if ws['source'] not in sources:  # make new source entry
                    domain = re.findall('//(\S+?)/', ws['link'])[0]
                    name = domain.split('.')[-2] + '.' + domain.split('.')[-1]
                    y = {'name': name,
                         'link': ws['link'],
                         'type': 'free',
                         'epcount': 1,
                         'seasons': list((x['season_number'], )) }  #1-tuple
                    sources[ws['source']] = y
                else:  # increase epcount and ensure season is accounted for
                    sources[ws['source']]['epcount'] += 1
                    if x['season_number'] not in sources[ws['source']]['seasons']:
                        sources[ws['source']]['seasons'].append(x['season_number'])
            for ws in x['tv_everywhere_web_sources']:
                if ws['source'] not in sources:  # make new source entry
                    domain = re.findall('//(\S+?)/', ws['link'])[0]
                    name = domain.split('.')[-2] + '.' + domain.split('.')[-1]
                    y = {'name': name,
                         'link': ws['link'],
                         'type': 'tv_provider',
                         'epcount': 1,
                         'seasons': list((x['season_number'], )) }  #1-tuple
                    sources[ws['source']] = y
                else:  # increase epcount and ensure season is accounted for
                    sources[ws['source']]['epcount'] += 1
                    if x['season_number'] not in sources[ws['source']]['seasons']:
                        sources[ws['source']]['seasons'].append(x['season_number'])

        # after interating all episodes, clean the sources
        for s in sources.keys():
            sources[s]['seasons'].sort()  # sort the seasons

            # convert seasons to string so template can display
            strseasons = list()
            for x in sources[s]['seasons']:
                strseasons.append(str(x))

            # if seasons are contiguous, then make into a range
            x, end = (0, 0)
            lst = strseasons
            for y in range(1, len(lst)-x):
                if int(lst[x]) + y == int(lst[x+y]): end = y
            if end:  # if first entry has subsequent contiguous
                lst[x] = lst[x] + '-' + lst[end]
                for z in range(x+1, end+1):
                    del lst[x+1]

            sources[s]['seasons'] = list(strseasons)  # overwrite w/ str list

            # remove sources that do not work
            if (sources[s]['name'] == unicode('cc.com') and
                    sources[s]['type'] == 'tv_provider'):
                    continue  #    del sources[s]
            elif (sources[s]['name'] == unicode('directv.com') and
                    sources[s]['type'] == 'free'):
                del sources[s]
            elif (sources[s]['name'] == unicode('fox.com') and
                    sources[s]['type'] == 'tv_provider'):
                del sources[s]

        m = medias['results'][0]
        med = {'title': m['title'], 'year': m['first_aired'][:4],
               'imdb': m['imdb_id'], 'img': m['artwork_208x117']}

    # alter display name of sources and limit what is displayed
    labels = {'netflix': 'Netflix',
              'hbo_now': 'HBO (and Amazon + HBO)',
              'hulu_plus': 'Hulu',
              'amazon_prime': 'Amazon Prime',
              'showtime_subscription': 'Showtime (and Amazon/Hulu + Showtime)'}
    for k in sources.keys():
        if k in labels.keys():
            sources[k]['name'] = labels[k]
        else:
            #del sources[k]  # allow others for free, but clean up some
            if sources[k]['name'] == 'showtime_amazon_prime': del sources[k]
            elif sources[k]['name'] == 'hulu_with_showtime': del sources[k]
            elif sources[k]['name'] == 'hbo_amazon_prime': del sources[k]

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

    return render_template('index.html', sources=sources, media=med,
                           query=query, qtype=qtype,
                           other_results=other_results[:4], isresult=1)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8181)
