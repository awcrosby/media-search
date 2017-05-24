#!/usr/bin/env python
from flask import Flask, render_template, request
import json
import guidebox
import time
import urllib
import pymongo
import pprint
from show_episodes import get_all_ep
app = Flask(__name__)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q')  # request.args.get returns unicode

    # type param comes from either button display name or 'did you mean' links
    qtype = 'show' if 'show' in request.args.get('type').lower() else 'movie'

    if not query:  # exit early if query is blank
        return render_template('index.html')

    guidebox.api_key = json.loads(open('apikeys.json').read())['guidebox']
    src = []  # list to hold dictionary of sources

    start = time.time()
    client = pymongo.MongoClient('localhost', 27017)
    db = client.MediaData

    # if movie perform movie search
    if qtype == 'movie':
        results = guidebox.Search.movies(precision='fuzzy',
                                         field='title', query=query)
        if not (results['total_results'] > 0):  # exit early if no results
            return render_template('index.html', isresult=0,
                                   query=query, qtype=qtype)
        gbid = results['results'][0]['id']  # take first result

        # get movie from mongodb, or api search and add to mongodb
        media = db.Movies.find_one({'id': gbid})
        if not media:
            media = guidebox.Movie.retrieve(id=gbid)
            m = media.copy()  # keeps media JSON serializable, pymongo alters
            db.Movies.insert_one(m).inserted_id  # this returns unique db id
        print 'movie db/api request time: ', time.time() - start

        # add sources to src list, text from api is unicode
        source_types = ['subscription_web_sources',
                        'free_web_sources',
                        'tv_everywhere_web_sources']
        for source_type in source_types:
            for s in media[source_type]:
                y = {'source': s['source'],
                     'display_name': s['display_name'],
                     'link': s['link'],
                     'type': source_type}
                src.append(y)

        # set media info to send to template
        med = {'title': media['title'],
               'year': media['release_year'],
               'imdb': media['imdb'],
               'img': media['poster_120x171']}

    # if show then perform show search across all episodes
    elif qtype == 'show':
        results = guidebox.Search.shows(precision='fuzzy', field='title',
                                        query=query)
        if not (results['total_results'] > 0):  # exit early if no results
            return render_template('index.html', isresult=0,
                                   query=query, qtype=qtype)
        show = results['results'][0]  # take first result
        gbid = show['id']

        # get show from mongodb, or api search and add to mongodb
        media = db.Shows.find_one({'id': gbid})
        if not media:
            media = get_all_ep(gbid)
            m = media.copy()  # keeps media JSON serializable, pymongo alters
            db.Shows.insert_one(m)
        print 'show db/api request time: ', time.time() - start

        # iterate all episodes, add source types: sub, free, tv_provider
        epcount, seasons = ({}, {})
        for ep in media['results']:
            if ep['season_number'] == 0:  # skips season 0 tv specials
                continue

            source_types = ['subscription_web_sources',
                            'free_web_sources',
                            'tv_everywhere_web_sources']
            for source_type in source_types:
                for s in ep[source_type]:
                    # if source not exist setup new source and seasons
                    if not any(d.get('source', None) ==
                               s['source'] for d in src):
                        newsource = {'source': s['source'],
                                     'display_name': s['display_name'],
                                     'link': s['link'],
                                     'type': source_type}
                        src.append(newsource)
                        seasons[s['source']] = []
                    # create or update epcount, append season if not there
                    epcount[s['source']] = epcount.get(s['source'], 0) + 1
                    if ep['season_number'] not in seasons[s['source']]:
                        seasons[s['source']].append(ep['season_number'])

        # for each source, set episode count and seasons
        for s in src:
            s['epcount'] = epcount[s['source']]  # set the source dict epcount
            s['seasons'] = seasons[s['source']]  # set the source dict seasons
            s['seasons'].sort()  # sort the seasons

            # convert seasons to string so template can display
            sea = list()
            for x in s['seasons']:
                sea.append(str(x))

            # if first entry has contiguous season, make those into a range
            contig = 0
            for y in range(1, len(sea)):  # find if/loc of last contig season
                if int(sea[0]) + y == int(sea[y]):
                    contig = y
            if contig:  # if contig then replace with range
                sea[0] = sea[0] + '-' + sea[contig]
                for z in range(1, contig+1):
                    del sea[1]

            s['seasons'] = list(sea)  # overwrite w/ str list

        # set media info to send to template
        m = results['results'][0]
        med = {'title': m['title'], 'year': m['first_aired'][:4],
               'imdb': m['imdb_id'], 'img': m['artwork_208x117']}

    # delete redundant hbo/showtime sources, and sources that don't work
    redundant_or_broken_src = ['hbo_amazon_prime',
                               'showtime_amazon_prime',
                               'hulu_with_showtime',
                               'showtime',  # tv_provider
                               'hbo',  # tv_provider, hbogo
                               'directv_free',
                               'comedycentral_tveverywhere',
                               'fox_tveverywhere']
    src = [s for s in src if not s['source'] in redundant_or_broken_src]

    # split sources into separate lists for template UI
    source_sub, source_free, source_tvp = ([], [], [])
    for s in src:
        if s['type'] == 'subscription_web_sources':
            source_sub.append(s)
        elif s['type'] == 'free_web_sources':
            source_free.append(s)
        elif s['type'] == 'tv_everywhere_web_sources':
            source_tvp.append(s)

    # build other_results to send to template
    other_results = []
    for m in results['results'][1:]:
        q_percent_enc = urllib.quote(m['title'].encode('utf-8'))
        x = {'link': 'search?q=' + q_percent_enc + '&type=' + qtype,
             'title': m['title']}
        # if (m['wikipedia_id'] != 0) and (m['wikipedia_id'] is not None):
        other_results.append(x)  # only keep if not very obscure

    # logs dictionaries retrieved, either from db or api
    logResults = open('logs/results.txt', 'w')
    pprint.pprint(results, logResults)
    logResults.close()
    logMedia = open('logs/media.txt', 'w')
    pprint.pprint(media, logMedia)
    logMedia.close()

    return render_template('index.html', media=med,
                           query=query, qtype=qtype,
                           other_results=other_results[:4], isresult=1,
                           source_sub=source_sub, source_free=source_free,
                           source_tvp=source_tvp)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8181)
