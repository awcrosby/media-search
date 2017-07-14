#!/usr/bin/env python
import sys
import requests
#import requests_cache
from bs4 import BeautifulSoup
import pymongo
import json
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

    #requests_cache.install_cache('scraper_cache')

    # get titles for particular source - function for each source
    # browse source libary by genre (may need to simulate scroll ex 144vs332 drama before/after scroll)
    # first page for poc: http://www.sho.com/movies/music
    # big_5: netflix, hulu, hbo, showtime, amz
    # other?: starz, cinemax, any amz channel, amc (very limited episodes)
    # later: num_episodes, num_seasons, link
    base_url = 'http://www.sho.com'
    r = requests.get(base_url + '/movies')
    soup = BeautifulSoup(r.text, 'html.parser')
    full_mov_lib = soup.find('section', {'data-context': 'slider:genres'})
    genre_links = full_mov_lib.find_all('a', {'class': 'promo__link'})
    genre_links = [a['href'] for a in genre_links]
    genre_links = ['/movies/music']  #TESTING

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
    titles = []
    for link in genre_links:
        r = requests.get(base_url + link)
        soup = BeautifulSoup(r.text, 'html.parser')
        divs = soup.find_all('div', {'class': 'movies-gallery__title'})
        for div in divs:
            titles.append(div.text)
    import q; q.d()

    tmdb_url = 'https://api.themoviedb.org/3/search/'
    params = {
        'api_key': json.loads(open('apikeys.json').read())['tmdb'],
        'query': titles[0]
    }
    mv = requests.get(tmdb_url+'movie', params=params).json()


    # capture all titles (nf = .video-preload-title-label)
    # return [{'title': 'Reservoir Dogs', 'mtype': 'movie'}, ...]

    # append mids to title list
    # search tmdb-api w/ title, take top result (some wrong accept it), append mid+
    # return [{'title': 'Reservoir Dogs'[new], 'mtype': 'movie', 'mid': 57616, 'year': 1991}]

    # determine mids
    '''source_mids[] = [... titles[]]
    db_mids[] = [db query by mtype]
    source_mids_not_in_db = []
    db_mids_also_in_source = []
    db_mids_not_in_source = []'''

    # for source_mids_not_in_db, add new media
    # for db_mids_not_in_source, remove source if exist
    # for db_mids_also_in_source, add source if not exist


    ''' one-time db statements: create/view indexes, del all docs in col '''
    # db.Media.create_index([('mtype', pymongo.ASCENDING), ('mid', pymongo.ASCENDING)])
    # print sorted(list(db.Shows.index_information()))
    # print db.Shows.delete_many({})  # delete all shows in database
    # print db.Movies.delete_many({})  # delete all movies in database
    # import q; q.d()

    # Media {
    #   'mid': 123
    #   'mtype': 'movie'
    #   'title': 'Reservoir Dogs'
    #   'year': 1991
    #   'sources': 
    #     [
    #       'netflix':
    #         {
    #            'display_name': "Netflix"
    #         }
    #     ]
    # }






    ''' Section for movies
    mv_new, mv_to_update, sh_new, sh_to_update = ([], [], [], [])
    # get list of new popular movies to add to database
    mov_limit = 2500
    page_len = 100
    mv_pop = guidebox.Movie.list(limit=page_len)  # initial dictionary
    for i in range(1, mov_limit/page_len):  # more pages if needed
        nextpage = guidebox.Movie.list(limit=page_len, offset=page_len*i)
        mv_pop['results'] += nextpage['results']
    mv_pop = [m['id'] for m in mv_pop['results']]
    mv_db = [m['id'] for m in db.Movies.find()]
    mv_new = list(set(mv_pop) - set(mv_db))

    # for all new movies get guidebox info and write to mongodb
    for gbid in mv_new:
        mov_detail = guidebox.Movie.retrieve(id=gbid)
        db.Movies.insert_one(mov_detail)
        logging.info('movie added: ' + mov_detail['title'])

    # get movie ids with updates / to update
    mv_chg = get_updates(obj='movie', typ='changes', time=time_ago)
    mv_chg = [m['id'] for m in mv_chg['results']]
    mv_db = [m['id'] for m in db.Movies.find()]
    mv_to_update = list(set(mv_chg) & set(mv_db))

    # del from mongodb and replace movies that have updates
    for gbid in mv_to_update:
        db.Movies.remove({'id': gbid})
        mov_detail = guidebox.Movie.retrieve(id=gbid)
        db.Movies.insert_one(mov_detail)
        logging.info('movie updated: ' + mov_detail['title'])'''

    '''# log database counts
    logging.info('movies added: ' + str(len(mv_new)))
    logging.info('movies updated: ' + str(len(mv_to_update)))
    logging.info('shows added: ' + str(len(sh_new)))
    logging.info('shows updated: ' + str(len(sh_to_update)))
    logging.info('database counts - movies: ' + str(db.Movies.count()) +
                 ', shows: ' + str(db.Shows.count()))'''


if __name__ == "__main__":
    main()
