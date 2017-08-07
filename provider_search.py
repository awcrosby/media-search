#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import requests
import requests_cache
from bs4 import BeautifulSoup
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
    update_watchlist_amz()
    flaskapp.remove_hulu_addon_media()


def update_watchlist_amz():
    # for all unique watchlist items check if amz is a source and add to db
    wl_unique = flaskapp.get_all_watchlist_in_db()
    for m in wl_unique:
        media = flaskapp.themoviedb_lookup(m['mtype'], m['id'])
        flaskapp.check_add_amz_source(media)
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
    # get unique: list of dict into list of tuples, set, back to dict
    logging.info('len(medias) before take unique: ' + str(len(medias)))
    medias = [dict(t) for t in set([tuple(d.items()) for d in medias])]
    logging.info('len(medias) after take unique: ' + str(len(medias)))

    for m in medias:
        time.sleep(0.2)
        results = flaskapp.themoviedb_search(m['title'], mtype)

        # exit iteration if search not complete or no results
        if 'total_results' not in results:
            logging.error('tmdb search not complete ' + mtype + ': ' + m['title'])
            continue
        if results['total_results'] < 1:
            logging.warning('tmdb 0 results for ' + mtype + ': ' + m['title'])
            continue

        # assume top result is best match and use it
        full_media = results['results'][0]

        # append data so dict can be saved to database
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
        t1 = t1.lower().replace('&', 'and')
        t2 = full_media['title'].translate({ord(c): None for c in "'’:"})
        t2 = t2.lower().replace('&', 'and')
        if t1 != t2:
            logging.warning('not exact titles: ' +
                            full_media['title'] + ' | ' + m['title'])

        # write db media if new
        flaskapp.insert_media_if_new(full_media)  # TODO test on next scrape

        # update source with specific media link, if available
        source_to_write = dict(source)
        if 'link' in m.keys():
            source_to_write['link'] = m['link']

        print 'in lookup', source_to_write
        print 'id: ', full_media['id']
        print 'full_media', full_media

        # update db media with source    TODO test on next scrape
        flaskapp.update_media_with_source(full_media, source_to_write)


'''
=amz searches and issues with multiple approaches:=
"Clear and Present Danger 1994" = no result, amz moviepage year=null | "Gang ~NY 2002" none amz has 2003 (yr diff)
"Benjamin Button" the result has year=2009, but amz moviepage year=2008 (as does tmdb), amz only gives rel date that changes
"Snowden" the result has year=2007, diff product than 2016 movie, false pos unless compare year
"Snowden 2016", no match (good)
"Deadpool 2016" response is "~Clip: Drawing Deadpool", suggests to compare exact titles
"Zoolander 2" response is "Zoolander No. 2: The Magnum Edition", suggest to not compare exact titles
"The Terminator 1984", top result is "Terminator Genisys"
Title | Keyword director search fixes all above, adds some issues but seem not as big:
-"Creed | Ryan Coogler" has a documentary about the movie as top result w/ no year, false neg
-"The Age of Adaline | Lee Toland Krieger" has no results since director not returned by amz, false neg
-misspelled dir names, fasle negs: "Contract Killer" jet lei, "Terminator Genisys", "Maya the Bee Movie"
'''


if __name__ == "__main__":
    main()
