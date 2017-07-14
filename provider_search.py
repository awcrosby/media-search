#!/usr/bin/env python
import sys
import requests
import requests_cache
from bs4 import BeautifulSoup
import pymongo
import json
import re
from pprint import pprint
import time
import logging

'''provider_search.py goes to media providers to
    search for media availability and write to db''' 


def main():
    # connect to mongodb, set logging config
    db = pymongo.MongoClient('localhost', 27017).MediaData
    logging.basicConfig(filename='/home/awcrosby/media-search/'
                        'log/provider_search.log',
                        format='%(asctime)s %(levelname)s: %(message)s',
                        level=logging.INFO)
    requests_cache.install_cache('demo_cache')

    ''' get titles for particular source - function for each source
        big_5 then other?: crackle, starz, cinemax, amzchannels, amc (limited ep)'''

    # ##### showtime media scraping #####
    base_url = 'http://www.sho.com'
    r = requests.get(base_url + '/movies')
    soup = BeautifulSoup(r.text, 'html.parser')
    full_mov_lib = soup.find('section', {'data-context': 'slider:genres'})

    # get all movie genre pages
    genre_links = full_mov_lib.find_all('a', {'class': 'promo__link'})
    genre_links = [a['href'] for a in genre_links]
    genre_links = [i for i in genre_links if 'adult' not in i]
    #genre_links = ['/movies/music']  #TESTING

    # for all root genre pages, get extra pagination links to scrape
    all_extra_pages = []
    for link in genre_links:
        r = requests.get(base_url + link)
        soup = BeautifulSoup(r.text, 'html.parser')
        extra_pages = soup.find('ul', 'pagination__list')
        if extra_pages:
            extra_pages = extra_pages.find_all('a')
            extra_pages = [a['href'] for a in extra_pages]
            all_extra_pages.extend(extra_pages)
    genre_links.extend(all_extra_pages)

    # for all root and extra genre pages, get movie titles
    titles = []
    for link in genre_links:
        r = requests.get(base_url + link)
        soup = BeautifulSoup(r.text, 'html.parser')
        divs = soup.find_all('div', {'class': 'movies-gallery__title'})
        for div in divs:
            titles.append(div.text.strip())


    # ##### TODO make into function #####

    # turn list of title text into list of dictionaries
    tmdb_url = 'https://api.themoviedb.org/3/search/'
    params = {'api_key': json.loads(open('apikeys.json').read())['tmdb']}
    source_media = []
    titles = set(titles)  # keeps unique, movies listed in multi genres
    for title in titles:
        if re.search('\([0-9][0-9][0-9][0-9]\)$', title):
            title_year = title[-5:-1]
            title = title[:-6].strip()
            params['year'] = title_year
        # get media dict from themoviedb, sleep due to api rate limit
        params['query'] = title
        time.sleep(0.2)
        search = requests.get(tmdb_url+'movie', params=params).json()
        params.pop('year', None)  # clears year if user

        # exit iteration if no results
        if search['total_results'] < 1:
            print title, '- themoviedb returned 0 results'
            continue

        # append data so dict can be saved to database
        m = search['results'][0]
        mtype = 'movie'  # TEMP
        m['mtype'] = mtype
        m['sources'] = []
        if mtype == 'movie':
            m['year'] = m['release_date'][:4]
        else:
            m['title'] = m['name']
            m['year'] = m['first_air_date'][:4]

        # build source_media dictionary
        source_media.append(m)

    # write db media if new
    for m in source_media:
        if not db.Media.find_one({'mtype': m['mtype'], 'id': m['id']}):
            db.Media.insert_one(m)

    # build source dict for current provider
    source = {'source': 'showtime_subscription',
              'display_name': 'Showtime',
              'link': 'http://www.showtime.com',
              'type': 'subscription_web_sources'}

    # update db media with source
    for m in source_media:
        db_media = db.Media.find_one({'mtype': m['mtype'], 'id': m['id']})
        if source not in db_media['sources']:
            db.Media.find_one_and_update({'mtype': m['mtype'], 'id': m['id']},
                {'$push': {'sources': source}})

    import q; q.d()

    ''' example scrape: clear database, get 800 sho titles then tmdb media,
    see none in db, append 'mtype' and add, then add source to all
    now get 500 hbo, for the 100 overlap it will not add to db, 400 will add
    now add source to all 500 '''

    ''' later maybe remove sources so no need to clear db if want to run one source
    -from db get: db_mv_mids and db_sh_mids
    -from scrape make: pr_mv_mids and pr_sh_mids
    -for set(db_mv_mids - pr_mv_mids): remove source
    -for set(db_sh_mids - pr_sh_mids): remove source '''

    ''' one-time db statements: create/view indexes, del all docs in col '''
    # db.Media.create_index([('mtype', pymongo.ASCENDING), ('id', pymongo.ASCENDING)])
    # print sorted(list(db.Shows.index_information()))
    # print db.Media.delete_many({})  # delete all shows in database
    # print db.Media.count()
    # import q; q.d()

    ''' Media {
         'id': 123
         'mtype': 'movie'
         'title': 'Reservoir Dogs'
         'year': 1991
         'sources': [
           {
             'source': 'netflix',
             'display_name': 'Netflix'
             #later: link, num_episodes, seasons[]
           }
         ]'''


if __name__ == "__main__":
    main()
