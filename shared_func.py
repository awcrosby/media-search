#!/usr/bin/env python
import json
import guidebox
import pymongo
import time
import logging

'''shared functionality between web flaskapp and backend db_update script'''


def get_media(gbid, mtype):
    # prepare for database and api access
    client = pymongo.MongoClient('localhost', 27017)
    db = client.MediaData
    guidebox.api_key = json.loads(open('apikeys.json').read())['guidebox']
    start = time.time()

    # get media details from mongodb, or api search + add to mongodb
    if mtype == 'movie':
        media = db.Movies.find_one({'id': gbid})
        if not media:
            media = guidebox.Movie.retrieve(id=gbid)
            db.Movies.insert_one(media.copy())  # copy keeps JSON serializeable
            logging.info('movie added: ' + media['title'])
        logging.info('movie db/api request time: ' + str(time.time() - start))
        print 'movie db/api request time: ', time.time() - start
    elif mtype == 'show':
        media = db.Shows.find_one({'id': gbid})
        if not media:
            media = get_show_ep(gbid)
            db.Shows.insert_one(media.copy())  # copy keeps JSON serializeable
            logging.info('show added: ' + media['title'])
        logging.info('show db/api request time: ' + str(time.time() - start))
        print 'show db/api request time:', time.time() - start, 'gbid:', gbid

    return media


def add_src_display(media, mtype):
    # set source types to look for, init src_display_list
    source_types = ['subscription_web_sources',
                    'free_web_sources',
                    'tv_everywhere_web_sources']
    src_display = []

    # build src_display for movie
    if mtype == 'movie':
        media['year'] = media['release_year']
        media['img'] = media['poster_120x171']
        for source_type in source_types:
            for s in media[source_type]:
                y = {'source': s['source'],
                     'display_name': s['display_name'],
                     'link': s['link'],
                     'type': source_type}
                src_display.append(y)

    # build src_display for show, iterating over all episodes
    elif mtype == 'show':
        epcount, seasons = ({}, {})
        for ep in media['results']:
            if ep['season_number'] == 0:  # skips season 0 tv specials
                continue

            for source_type in source_types:
                for s in ep[source_type]:
                    # if source not exist setup new source and seasons
                    if not any(d.get('source', None) ==
                               s['source'] for d in src_display):
                        newsource = {'source': s['source'],
                                     'display_name': s['display_name'],
                                     'link': s['link'],
                                     'type': source_type}
                        src_display.append(newsource)
                        seasons[s['source']] = []
                    # create or update epcount, append season if not there
                    epcount[s['source']] = epcount.get(s['source'], 0) + 1
                    if ep['season_number'] not in seasons[s['source']]:
                        seasons[s['source']].append(ep['season_number'])

        # for each source, set episode count and seasons
        for s in src_display:
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

    # delete redundant hbo/showtime sources, and sources that don't work
    redundant_or_broken_src = ['hbo_amazon_prime',
                               'showtime_amazon_prime',
                               'hulu_with_showtime',
                               'showtime',  # tv_provider
                               'hbo',  # tv_provider, hbogo
                               'directv_free',
                               'comedycentral_tveverywhere',
                               'fox_tveverywhere']
    src_display = [s for s in src_display
                   if not s['source'] in redundant_or_broken_src]

    # sort src_display
    s1 = [s for s in src_display if s['type'] == 'subscription_web_sources']
    s2 = [s for s in src_display if s['type'] == 'tv_everywhere_web_sources']
    s3 = [s for s in src_display if s['type'] == 'free_web_sources']
    src_display = s1 + s2 + s3

    # append to media src_display and mtype
    media['src_display'] = src_display
    media['mtype'] = mtype

    return media


def get_show_ep(gbid):
    guidebox.api_key = json.loads(open('/home/awcrosby/media-search/'
                                  'apikeys.json').read())['guidebox']

    # get high-level show info, get episodes for show
    show = guidebox.Show.retrieve(id=gbid)
    show_ep = get_all_ep(gbid)

    # add high-level show info to dict with all episodes
    show_ep['id'] = gbid  # add a key to dictionary to allow lookup
    show_ep['imdb_id'] = show['imdb_id']
    show_ep['title'] = show['title']
    show_ep['year'] = show['first_aired'][:4]
    show_ep['img'] = show['artwork_208x117']
    show_ep['overview'] = show['overview']

    return show_ep


def get_all_ep(gbid):
    guidebox.api_key = json.loads(open('/home/awcrosby/media-search/'
                                  'apikeys.json').read())['guidebox']

    # get dictionary with many episodes
    page_len = 100
    episodes = guidebox.Show.episodes(id=gbid, include_links=True,
                                      reverse_ordering=True,
                                      limit=page_len)

    # get more pages of ep, only if results are greater than page_len
    for i in range(1, episodes['total_results']/page_len + 1):
        nextpage = guidebox.Show.episodes(id=gbid, include_links=True,
                                          reverse_ordering=True,
                                          limit=page_len,
                                          offset=page_len*i)
        episodes['results'] += nextpage['results']

    return episodes
