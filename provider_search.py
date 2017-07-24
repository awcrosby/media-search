#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import requests
import requests_cache
from bs4 import BeautifulSoup
import pymongo
import json
import re
from pprint import pprint
import time
import random
import logging
from selenium import webdriver

'''provider_search.py goes to media providers to
    search for media availability and write to db''' 


def main():
    logging.basicConfig(filename='/home/awcrosby/media-search/'
                        'log/provider_search.log',
                        format='%(asctime)s %(levelname)s: %(message)s',
                        level=logging.INFO)
    requests_cache.install_cache('demo_cache')

    ''' get titles for particular source - function for each source
        big_5 then other?: crackle, starz, cinemax, amzchannels, amc (limited ep)'''

    #search_hbo()
    #search_showtime()
    #search_netflix()
    search_hulu()


def search_hulu():
    # source dict to be added to media sources[] in db for found titles
    source = {'source': 'hulu',
              'display_name': 'Hulu',
              'link': 'http://www.hulu.com',
              'type': 'subscription_web_sources'}

    # go to hulu splash page
    driver = webdriver.PhantomJS()
    driver.set_window_size(1920, 1080)
    driver.get('https://www.hulu.com')
    time.sleep(1.2)

    # click on log in link
    links = driver.find_elements_by_tag_name('a')
    links[2].click()
    time.sleep(1.2)
    logging.info('hulu, clicked on log in link')

    # switch to pop-up iframe with login info
    iframe = driver.find_element_by_id('login-iframe')
    driver.switch_to_frame(iframe)

    # click on dummy input to make real input visible
    driver.find_element_by_name('dummy_login').click()

    # enter credentials and click login div
    driver.find_element_by_id('user_email').send_keys('boombox200@gmail.com')
    driver.find_element_by_id('password').send_keys('4!A$@AV7DG')
    logging.info('hulu, pasted u/p')
    driver.save_screenshot('static/screenshot.png')
    # driver.find_element_by_id('recaptcha_response_field').send_keys('')
    login_anchor = driver.find_element_by_class_name('login')
    login_anchor.find_element_by_tag_name('div').click()
    time.sleep(1.2)

    # switch out of iframe and click profile link
    driver.switch_to_default_content()
    driver.find_element_by_id('98994228').click()
    time.sleep(1.2)
    logging.info('hulu, clicked profile')
    driver.save_screenshot('static/screenshot2.png')


    # MOVIE SEARCH SECTION
    # get all movie genres
    driver.get('https://www.hulu.com/movies/genres')
    time.sleep(1.5)
    all_genre = driver.find_element_by_id('all_movies_genres')
    anchors = all_genre.find_elements_by_class_name('beacon-click')
    genre_pages = [a.get_attribute('href') for a in anchors]
    print 'genre_pages:', genre_pages
    logging.info('hulu, got movie genres')
    #import q; q.d()

    media = []
    for page in genre_pages[:2]:
        # get page and pointer to top panel, holding about 6 medias
        driver.get(page)
        logging.info('did GET on: ' + page)
        time.sleep(3)
        top_panel = driver.find_elements_by_class_name('tray')[0]
        next_btn = top_panel.find_element_by_class_name('next')

        while True:
            thumbnails = top_panel.find_elements_by_class_name('row')
            for t in thumbnails:
                try:
                    title = t.find_element_by_class_name('title')
                    title = title.get_attribute('innerHTML')
                    link = t.find_element_by_class_name('beacon-click')
                    link = link.get_attribute('href')
                    media += [{'title': title, 'link': link}]
                except Exception as err:
                    logging.error(err.message)
                    pass
            # exit loop if next button is not displayed, otherwise click/wait
            if not next_btn.is_displayed():
                break
            next_btn.click()
            time.sleep(float(random.randrange(1500, 2000, 1))/1000)
        logging.info(str(len(media)) + ' len(media) for page: ' + page)

    # list of dict into list of tuples, take unique set, then back to dict
    media = [dict(t) for t in set([tuple(d.items()) for d in media])]

    import q; q.d()
    driver.quit()

    # put source into beautifulsoup and get titles
    #soup = BeautifulSoup(driver.page_source, 'html.parser')

def search_netflix():
    # source dict to be added to media sources[] in db for found titles
    source = {'source': 'netflix',
              'display_name': 'Netflix',
              'link': 'http://www.netflix.com',
              'type': 'subscription_web_sources'}

    # log in to provider
    driver = webdriver.PhantomJS()
    driver.set_window_size(1920, 1080)
    driver.get('https://www.netflix.com/login')
    inputs = driver.find_elements_by_tag_name('input')
    inputs[0].send_keys('boombox200@gmail.com')
    inputs[1].send_keys('BJUXSkjnD_9t')
    driver.find_element_by_tag_name('button').click()
    
    # MOVIE SEARCH SECTION
    genre_pages = [
                   'https://www.netflix.com/browse/genre/1365',  # action
                   'https://www.netflix.com/browse/genre/5763',  # drama
                   'https://www.netflix.com/browse/genre/7077',  # indie
                   'https://www.netflix.com/browse/genre/8711',  # horror
                   'https://www.netflix.com/browse/genre/6548',  # comedy
                   'https://www.netflix.com/browse/genre/31574',  # classics
                   'https://www.netflix.com/browse/genre/7424',  # anime
                   'https://www.netflix.com/browse/genre/783',  # kid
                   'https://www.netflix.com/browse/genre/7627',  # cult
                   'https://www.netflix.com/browse/genre/6839',  # docs ~1321
                   'https://www.netflix.com/browse/genre/5977',  # gay
                   'https://www.netflix.com/browse/genre/78367', # internat'l
                   'https://www.netflix.com/browse/genre/8883',  # romance
                   'https://www.netflix.com/browse/genre/1492',  # scifi
                   'https://www.netflix.com/browse/genre/8933'  # thrillers
                  ]

    titles = []  # TODO replace this with a dictionary of what found in scrape
    for page in genre_pages:
        # get initial page and scroll to bottom many times
        driver.get(page)
        for i in range(36):
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(float(random.randrange(90, 140, 1))/100)

        # put source into beautifulsoup and get titles
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        divs = soup('div', 'video-preload-title-label')
        print len(divs), 'titles on page:', page
        titles += [d.text for d in divs]

    medias = get_medias_from_titles(titles, mtype='movie')
    medias_to_db_with_source(medias, source)

    # SHOW SEARCH SECTION
    genre_pages = ['https://www.netflix.com/browse/genre/83']  # tv ~1500
    titles = []
    for page in genre_pages:
        # get initial page and scroll to bottom many times
        driver.get(page)
        for i in range(40):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(float(random.randrange(90, 140, 1))/100)

        # put source into beautifulsoup and get titles
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        divs = soup('div', 'video-preload-title-label')
        print len(divs), 'titles on page:', page
        titles += [d.text for d in divs]

    medias = get_medias_from_titles(titles, mtype='show')
    medias_to_db_with_source(medias, source)

    driver.quit()

 
def search_hbo():
    # source dict to be added to media sources[] in db for found titles
    source = {'source': 'hbo_now',
              'display_name': 'HBO',
              'link': 'http://www.hbo.com',
              'type': 'subscription_web_sources'}

    # MOVIE SEARCH SECTION
    pages = ['http://www.hbo.com/movies/catalog',
             'http://www.hbo.com/documentaries/catalog']
    for page in pages:
        r = requests.get(page)
        soup = BeautifulSoup(r.text, 'html.parser')

        # get script with full dictionary of all page data
        script = soup.find('script', {'data-id': 'reactContent'}).text

        # extract json from <script> response (after equals)
        data = json.loads(script[script.find('=')+1:])

        movies = data['content']['navigation']['films']
        titles = [m['title'] for m in movies if m['link']]
        medias = get_medias_from_titles(titles, mtype='movie')
        medias_to_db_with_source(medias, source)


    # SHOW SEARCH SECTION
    r = requests.get('http://www.hbo.com')
    soup = BeautifulSoup(r.text, 'html.parser')

    # get script with full dictionary of all page data
    script = soup.find('script', {'data-id': 'reactContent'}).text

    # extract json from <script> response (after equals)
    data = json.loads(script[script.find('=')+1:])

    shows = (data['navigation']['toplevel'][0]['subCategory'][0]['items'] +
             data['navigation']['toplevel'][0]['subCategory'][1]['items'])
    titles = [s['name'] for s in shows]
    medias = get_medias_from_titles(titles, mtype='show')
    medias_to_db_with_source(medias, source)


def search_showtime():
    # source dict to be added to media sources[] in db for found titles
    source = {'source': 'showtime_subscription',
              'display_name': 'Showtime',
              'link': 'http://www.showtime.com',
              'type': 'subscription_web_sources'}

    # MOVIE SEARCH SECTION
    base_url = 'http://www.sho.com'
    r = requests.get(base_url + '/movies')
    soup = BeautifulSoup(r.text, 'html.parser')

    # get all movie genre pages
    full_mov_lib = soup.find('section', {'data-context': 'slider:genres'})
    genre_links = full_mov_lib.find_all('a', {'class': 'promo__link'})
    genre_links = [a['href'] for a in genre_links]
    genre_links = [i for i in genre_links if 'adult' not in i]

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

    medias = get_medias_from_titles(titles, mtype='movie')
    medias_to_db_with_source(medias, source)


    # SHOW SEARCH SECTION
    r = requests.get(base_url + '/series')
    soup = BeautifulSoup(r.text, 'html.parser')
    all_series = soup.find('section',
        {'data-context': 'promo group:All Showtime Series'})

    # get all show titles
    title_links = all_series.find_all('a', {'class': 'promo__link'})
    titles = [a.text.strip() for a in title_links]

    medias = get_medias_from_titles(titles, mtype='show')
    medias_to_db_with_source(medias, source)


def get_medias_from_titles(titles, mtype):
    # TODO pass prov_dict={title:'a', link:'/mov', source_id:123}, mtype, source
    # (define source directly above call)
    # from title get tmdb id
    # clean db write with no source if new (combine 2 functions) write_media_from_titles()
    # now append the source based on new source[] created from d[link] and source
    # -maybe also append any other data found in prov_dict like source_id (later can see if source id in db)
    # -if d[link] null used link in source

    ''' later maybe remove sources so no need to clear db if want to run one source
    -from db get: db_mv_mids and db_sh_mids
    -from scrape make: pr_mv_mids and pr_sh_mids
    -for set(db_mv_mids - pr_mv_mids): remove source
    -for set(db_sh_mids - pr_sh_mids): remove source '''

    # setup for api to go from textal title to id
    tmdb_url = 'https://api.themoviedb.org/3/search/'
    params = {'api_key': json.loads(open('apikeys.json').read())['tmdb']}
    medias = []
    print 'len(titles) before unique: ', len(titles)
    titles = set(titles)  # keeps unique, since movies listed in multi genres
    print 'len(titles) after unique: ', len(titles)

    for title in titles:
        # if year is in title, remove from title and use as search param
        if re.search('\([0-9][0-9][0-9][0-9]\)$', title):
            title_year = title[-5:-1]
            title = title[:-6].strip()
            params['year'] = title_year

        # get media dict from themoviedb, sleep due to api rate limit
        params['query'] = title
        time.sleep(0.2)
        search_type = 'movie' if mtype == 'movie' else 'tv'
        search = requests.get(tmdb_url+search_type, params=params).json()
        params.pop('year', None)  # clears year if used

        # exit iteration if search not complete or no results
        if 'total_results' not in search:
            logging.error('tmdb search not complete ' + mtype + ': ' + title)
            continue
        if search['total_results'] < 1:
            logging.warning('tmdb 0 results for ' + mtype + ': ' + title)
            continue

        # append data so dict can be saved to database
        m = search['results'][0]
        m['mtype'] = mtype
        m['sources'] = []
        if mtype == 'movie':
            m['year'] = m['release_date'][:4]
        else:
            m['title'] = m['name']
            m['year'] = m['first_air_date'][:4]

        # build medias dictionary
        medias.append(m)
        logging.info('tmdb found ' + mtype + ': ' + title)

        # check if titles are not exact match, in future may not append these
        t1 = title.translate({ord(c): None for c in "'’:"})
        t2 = m['title'].translate({ord(c): None for c in "'’:"})
        if t1.lower().replace('&', 'and') != t2.lower().replace('&', 'and'):
            logging.warning('not exact titles: ' + title + ' | ' + m['title'])
    return medias


def medias_to_db_with_source(medias, source):
    db = pymongo.MongoClient('localhost', 27017).MediaData

    # write db media if new
    for m in medias:
        if not db.Media.find_one({'mtype': m['mtype'], 'id': m['id']}):
            db.Media.insert_one(m)
            logging.info('db wrote new media: ' + m['title'])

    # update db media with source
    for m in medias:
        db_media = db.Media.find_one({'mtype': m['mtype'], 'id': m['id']})
        if source not in db_media['sources']:
            db.Media.find_one_and_update({'mtype': m['mtype'], 'id': m['id']},
                {'$push': {'sources': source}})
            logging.info(source['source'] + ' added for: ' + m['title'])

    ''' example scrape: clear database, get 800 sho titles then tmdb media,
    see none in db, append 'mtype' and add, then add source to all
    now get 500 hbo, for the 100 overlap it will not add to db, 400 will add
    now add source to all 500 '''

    ''' one-time db statements: create/view indexes, del all docs in col '''
    # db.Media.create_index([('mtype', pymongo.ASCENDING), ('id', pymongo.ASCENDING)])
    # print sorted(list(db.Shows.index_information()))
    # print db.Media.delete_many({})  # delete all shows in database
    # print db.Media.count()
    # import q; q.d()


if __name__ == "__main__":
    main()
