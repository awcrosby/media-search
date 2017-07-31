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
import flaskapp

'''provider_search.py goes to media providers to
    search for media availability and write to db''' 


def main():
    logging.basicConfig(filename='/home/awcrosby/media-search/'
                        'log/provider_search.log',
                        format='%(asctime)s %(levelname)s: %(message)s',
                        level=logging.INFO)
    requests_cache.install_cache('demo_cache')

    #search_hbo()
    #search_showtime()
    #search_netflix()
    #search_hulu()
    #remove_hulu_addon_media()
    update_watchlist_amz()


def update_watchlist_amz():
    '''searches every watchlist media and checks if amazon is a source
    and if so adds to database'''

    # get list of all watchlist unique media
    db = pymongo.MongoClient('localhost', 27017).MediaData
    wl_cur = db.Users.find({}, {'_id':0, 'watchlist': 1})
    wl_all = []
    for wl in wl_cur:
        wl_all += wl['watchlist']
    print 'len(wl_all):', len(wl_all)
    wl_unique = [dict(t) for t in set([tuple(d.items()) for d in wl_all])]
    print 'len(wl_unique):', len(wl_unique)

    # send each media to check_add_amz_source with sleep for api limit
    for m in wl_unique:
        flaskapp.check_add_amz_source(m['title'], m['year'], m['mtype'])
        time.sleep(1.1)

    return


def search_hulu():
    # source dict to be added to media sources[] in db for found titles
    source = {'name': 'hulu',
              'display_name': 'Hulu',
              'link': 'http://www.hulu.com',
              'type': 'subscription_web_sources'}

    # go to hulu splash page
    driver = webdriver.PhantomJS()
    driver.implicitly_wait(10)  # seconds
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
    logging.info('hulu, got movie genres')

    medias = []
    for page in genre_pages:
        # get page and pointer to top panel, holding about 6 medias
        try:
            logging.info('about to get page: ' + page)
            driver.get(page)
            time.sleep(6)
            top_panel = driver.find_element_by_class_name('tray')
            next_btn = top_panel.find_element_by_class_name('next')
        except Exception as e:
            logging.exception('initial load of genre_page')
            pass

        # get visible media, click next, repeat until no next button
        while True:
            try:
                thumbnails = top_panel.find_elements_by_class_name('row')
                for t in thumbnails:
                    title = t.find_element_by_class_name('title')
                    title = title.get_attribute('innerHTML')
                    link = t.find_element_by_class_name('beacon-click')
                    link = link.get_attribute('href')
                    medias += [{'title': title, 'link': link}]
                if not next_btn.is_displayed():
                    break  # exit loop if next button is not displayed
                next_btn.click()
                time.sleep(float(random.randrange(1800, 2300, 1))/1000)
            except Exception as e:
                logging.exception('processing thumbnails of media')
                pass
        logging.info('len(medias) so far: ' + str(len(medias)))

    import q; q.d()
    lookup_and_write_medias(medias, mtype='movie', source=source)


    # SHOW SEARCH SECTION
    # get all show genres
    driver.get('https://www.hulu.com/tv/genres')
    time.sleep(1.5)
    all_genre = driver.find_element_by_id('all_tv_genres')
    anchors = all_genre.find_elements_by_class_name('beacon-click')
    genre_pages = [a.get_attribute('href') for a in anchors]
    logging.info('hulu, got tv genres')

    medias = []
    for page in genre_pages:
        if page == 'https://www.hulu.com/videogames':
            continue
        # get page and pointer to top panel, holding about 6 medias
        try:
            logging.info('about to get page: ' + page)
            driver.get(page)
            time.sleep(6)
            top_panel = driver.find_element_by_class_name('tray')
            next_btn = top_panel.find_element_by_class_name('next')
        except Exception as e:
            logging.exception('initial load of genre_page')
            pass

        # get visible media, click next, repeat until no next button
        while True:
            try:
                thumbnails = top_panel.find_elements_by_class_name('row')
                for t in thumbnails:
                    title = t.find_element_by_class_name('title')
                    title = title.get_attribute('innerHTML')
                    link = t.find_element_by_class_name('beacon-click')
                    link = link.get_attribute('href')
                    medias += [{'title': title, 'link': link}]
                if not next_btn.is_displayed():
                    break  # exit loop if next button is not displayed
                next_btn.click()
                time.sleep(float(random.randrange(1800, 2300, 1))/1000)
            except Exception as e:
                logging.exception('processing thumbnails of media')
                pass
        logging.info('len(medias) so far: ' + str(len(medias)))

    import q; q.d()
    lookup_and_write_medias(medias, mtype='show', source=source)
    driver.quit()


def remove_hulu_addon_media():
    '''on browse of hulu, for media requiring addons (i.e. showtime)
    it does not denote this in html (only in an img), so any overlaps
    with both sources will remove hulu as a source'''

    db = pymongo.MongoClient('localhost', 27017).MediaData
    x = db.Media.update_many({'sources.name': {'$all': ['hulu', 'showtime']}},
                         {'$pull': {'sources': {'name': 'hulu'}}})
    logging.info('hulu removed from {0!s} db docs'.format(x.matched_count))


def search_netflix():
    # source dict to be added to media sources[] in db for found titles
    base_url = 'http://www.netflix.com'
    source = {'name': 'netflix',
              'display_name': 'Netflix',
              'link': base_url,
              'type': 'subscription_web_sources'}

    # log in to provider
    driver = webdriver.PhantomJS()
    driver.implicitly_wait(10)  # seconds
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

    medias = []
    for page in genre_pages:
        # get initial page and scroll to bottom many times
        try:
            time.sleep(1.5)
            driver.get(page)
        except httplib.BadStatusLine as bsl:
            logging.error('get page error, will try to pass, msg= ' + bsl.message)
            pass
        logging.info('did get on page: ' + page)
        for i in range(36):
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(float(random.randrange(90, 140, 1))/100)

        # put source into beautifulsoup and get titles
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        divs = soup('div', 'ptrack-content')
        for d in divs:
            title = d.find('div', 'video-preload-title-label').text
            elements = d['data-ui-tracking-context'].split(',')
            vid_element = [i for i in elements if 'video_id' in i]
            netflix_id = vid_element[0][vid_element[0].find(':')+1:]
            link = base_url+'/title/'+netflix_id
            medias += [{'title': title, 'link': link}]
        logging.info('len(medias) so far: ' + str(len(medias)))

    lookup_and_write_medias(medias, mtype='movie', source=source)


    # SHOW SEARCH SECTION
    genre_pages = ['https://www.netflix.com/browse/genre/83']  # tv ~1500
    medias = []
    for page in genre_pages:
        # get initial page and scroll to bottom many times
        try:
            time.sleep(1.5)
            driver.get(page)
        except httplib.BadStatusLine as bsl:
            logging.error('get page error, will try to pass, msg= ' + bsl.message)
            pass
        logging.info('did get on page: ' + page)
        for i in range(40):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(float(random.randrange(90, 140, 1))/100)

        # put source into beautifulsoup and get titles
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        divs = soup('div', 'ptrack-content')
        for d in divs:
            title = d.find('div', 'video-preload-title-label').text
            elements = d['data-ui-tracking-context'].split(',')
            vid_element = [i for i in elements if 'video_id' in i]
            netflix_id = vid_element[0][vid_element[0].find(':')+1:]
            link = base_url+'/title/'+netflix_id
            medias += [{'title': title, 'link': link}]
        logging.info('len(medias) for page: ' + str(len(medias)))

    lookup_and_write_medias(medias, mtype='show', source=source)
    driver.quit()

 
def search_showtime():
    # source dict to be added to media sources[] in db for found titles
    base_url = 'http://www.sho.com'
    source = {'name': 'showtime',
              'display_name': 'Showtime',
              'link': base_url,
              'type': 'subscription_web_sources'}

    # MOVIE SEARCH SECTION
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
    catalog = []
    for link in genre_links:
        r = requests.get(base_url + link)
        soup = BeautifulSoup(r.text, 'html.parser')

        anchors = soup.find_all('a', {'class': 'movies-gallery__item'})
        for a in anchors:
            title = a['data-label']
            title = title[title.find(':')+1:]
            link = base_url + a['href']
            catalog += [{'title': title, 'link': link}]

    # check availability via link, build medias list
    medias = []
    for c in catalog:
        time.sleep(0.25)
        r = requests.get(c['link'])
        soup = BeautifulSoup(r.text, 'html.parser')
        if soup.find(text = 'STREAM THIS MOVIE'):
            medias += [c]

    lookup_and_write_medias(medias, mtype='movie', source=source)


    # SHOW SEARCH SECTION
    r = requests.get(base_url + '/series')
    soup = BeautifulSoup(r.text, 'html.parser')
    all_series = soup.find('section',
        {'data-context': 'promo group:All Showtime Series'})

    # get all show titles
    medias = []
    anchors = all_series.find_all('a', {'class': 'promo__link'})
    for a in anchors:
        title = a.text.strip()
        link = base_url + a['href']
        medias += [{'title': title, 'link': link}]

    lookup_and_write_medias(medias, mtype='show', source=source)


def search_hbo():
    # source dict to be added to media sources[] in db for found titles
    base_url = 'http://www.hbo.com'
    source = {'name': 'hbo',
              'display_name': 'HBO',
              'link': base_url,
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

        # get full movie catalog
        movies = data['content']['navigation']['films']
        catalog = [{'title': m['title'], 'link': base_url + '/' + m['link']}
                  for m in movies if m['link']]

        # check availability via movie link, build medias list
        medias = []
        for c in catalog:
            r = requests.get(c['link'])
            soup = BeautifulSoup(r.text, 'html.parser')
            if soup.find(text = 'NOW & GO'):
                medias += [c]

        lookup_and_write_medias(medias, mtype='movie', source=source)
    

    # SHOW SEARCH SECTION
    r = requests.get('http://www.hbo.com')
    soup = BeautifulSoup(r.text, 'html.parser')

    # get script with full dictionary of all page data
    script = soup.find('script', {'data-id': 'reactContent'}).text

    # extract json from <script> response (after equals)
    data = json.loads(script[script.find('=')+1:])

    # get all shows, with title and link
    shows = (data['navigation']['toplevel'][0]['subCategory'][0]['items'] +
             data['navigation']['toplevel'][0]['subCategory'][1]['items'])
    catalog = [{'title': m['name'], 'link': base_url + m['nav']}
             for m in shows]

    # check availability via link, build medias list
    medias = []
    for c in catalog:
        r = requests.get(c['link'])
        soup = BeautifulSoup(r.text, 'html.parser')
        if soup.find(text = 'NOW & GO'):
            medias += [c]

    lookup_and_write_medias(medias, mtype='show', source=source)


def lookup_and_write_medias(medias, mtype, source):
    # setup for api and database
    tmdb_url = 'https://api.themoviedb.org/3/search/'
    params = {'api_key': json.loads(open('apikeys.json').read())['tmdb']}
    db = pymongo.MongoClient('localhost', 27017).MediaData

    # get unique: list of dict into list of tuples, set, back to dict
    logging.info('len(medias) before take unique: ' + str(len(medias)))
    medias = [dict(t) for t in set([tuple(d.items()) for d in medias])]
    logging.info('len(medias) after take unique: ' + str(len(medias)))

    for m in medias:
        # if year is in title, remove from title and use as search param
        if re.search('\([0-9][0-9][0-9][0-9]\)$', m['title']):
            title_year = m['title'][-5:-1]
            m['title'] = m['title'][:-6].strip()
            params['year'] = title_year

        # lookup media dict from themoviedb, sleep due to api rate limit
        params['query'] = m['title']
        time.sleep(0.2)
        search_type = 'movie' if mtype == 'movie' else 'tv'
        search = requests.get(tmdb_url+search_type, params=params).json()
        params.pop('year', None)  # clears year if used

        # exit iteration if search not complete or no results
        if 'total_results' not in search:
            logging.error('tmdb search not complete ' + mtype + ': ' + m['title'])
            continue
        if search['total_results'] < 1:
            logging.warning('tmdb 0 results for ' + mtype + ': ' + m['title'])
            continue

        # append data so dict can be saved to database
        full_media = search['results'][0]
        full_media['mtype'] = mtype
        full_media['sources'] = []
        if mtype == 'movie':
            full_media['year'] = full_media['release_date'][:4]
        else:
            full_media['title'] = full_media['name']
            full_media['year'] = full_media['first_air_date'][:4]
        logging.info('tmdb found ' + mtype + ': ' + full_media['title'])

        # check if titles are not exact match, in future may not append these
        t1 = m['title'].translate({ord(c): None for c in "'’:"})
        t2 = full_media['title'].translate({ord(c): None for c in "'’:"})
        if t1.lower().replace('&', 'and') != t2.lower().replace('&', 'and'):
            logging.warning('not exact titles: ' +
                            full_media['title'] + ' | ' + m['title'])

        # write db media if new
        if not db.Media.find_one({'mtype': full_media['mtype'], 'id': full_media['id']}):
            db.Media.insert_one(full_media)
            logging.info('db wrote new media: ' + full_media['title'])

        # update source with specific media link, if available
        source_to_write = dict(source)
        if 'link' in m.keys():
            source_to_write['link'] = m['link']

        # update db media with source
        db_media = db.Media.find_one({'mtype': full_media['mtype'],
                                      'id': full_media['id']})
        if (db_media and not any(source['name'] in
                d.values() for d in db_media['sources'])):
            db.Media.find_one_and_update({'mtype': full_media['mtype'],
                                          'id': full_media['id']},
                {'$push': {'sources': source_to_write}})
            logging.info(source['name'] + ' added for: ' + full_media['title'])

    ''' one-time db statements: create/view indexes, del all docs in col '''
    # db.Media.create_index([('mtype', pymongo.ASCENDING), ('id', pymongo.ASCENDING)])
    # print sorted(list(db.Shows.index_information()))
    # print db.Media.delete_many({})  # delete all shows in database
    # print db.Media.count()


if __name__ == "__main__":
    main()
