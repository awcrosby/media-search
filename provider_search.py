#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import requests_cache
from bs4 import BeautifulSoup
import json
import time
import random
import logging
from selenium import webdriver
from selenium.common.exceptions import (NoSuchElementException,
                                        StaleElementReferenceException)
import flaskapp

with open('creds.json', 'r') as f:
    creds = json.loads(f.read())

'''provider_search.py goes to media providers to
   search for media availability and write to db'''


def main():
    logging.basicConfig(filename='/home/awcrosby/media-search/'
                        'log/provider_search.log',
                        format='%(asctime)s %(levelname)s: %(message)s',
                        level=logging.INFO)
    requests_cache.install_cache('demo_cache')

    search_hulu()
    search_netflix()
    search_showtime()
    search_hbo()
    update_watchlist_amz()
    flaskapp.remove_hulu_addon_media()
    flaskapp.reindex_database()


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

    # enter credentials and click login button
    popup = driver.find_element_by_id('login-popup-section')
    form = popup.find_element_by_tag_name('form')
    email_input = form.find_elements_by_tag_name('input')[0]
    pw_input = form.find_elements_by_tag_name('input')[1]
    email_input.send_keys(creds['hulu_u'])
    pw_input.send_keys(creds['hulu_p'])
    logging.info('hulu, pasted u/p')
    driver.save_screenshot('static/screenshot.png')
    # driver.find_element_by_id('recaptcha_response_field').send_keys('')
    form.find_element_by_tag_name('button').click()
    time.sleep(1.2)

    # switch out of iframe and click profile link
    driver.find_element_by_id('98994228').click()
    time.sleep(1.2)
    logging.info('hulu, clicked profile')
    driver.save_screenshot('static/screenshot2.png')

    def get_medias_from_genre_pages(genre_pages):
        medias = []
        for page in genre_pages:
            if page == 'https://www.hulu.com/videogames':
                continue
            if page == 'https://www.hulu.com/latino':
                continue  # says movie genre but shows not movies
            # get page and pointer to top panel, holding about 6 medias
            driver.get(page)
            logging.info('did get on page: {}'.format(page))
            time.sleep(8)
            top_panel = driver.find_element_by_class_name('tray')
            next_btn = top_panel.find_element_by_class_name('next')
            next_counter = 0

            # get visible media, click next, repeat until no next button
            while True:
                thumbnails = top_panel.find_elements_by_class_name('row')
                for t in thumbnails:
                    try:
                        title = t.find_element_by_class_name('title')
                        title = title.get_attribute('innerHTML')
                        # logging.info('title in html found: {}'.format(title))
                        link = t.find_element_by_class_name('beacon-click')
                        link = link.get_attribute('href')
                        medias += [{'title': title, 'link': link}]
                    except NoSuchElementException:
                        logging.warning('no title in row html, blank grid')
                        # with open('log/selenium_error_html_dump.txt',
                        #           'w') as f:
                        #    f.write(str(driver.page_source))
                        continue
                    except StaleElementReferenceException:
                        logging.error('missed a title, may need to wait more')
                        continue
                if not next_btn.is_displayed():
                    break  # exit loop if next button is not displayed
                next_btn.click()
                next_counter += 1
                if next_counter % 10 == 0:
                    logging.info('clicked next {} times'.format(next_counter))
                if next_counter >= 120:
                    logging.error('next button never went away, may have ' +
                                  'not gotten all media on: {}'.format(page))
                    break  # exit loop, pages should never be this long
                time.sleep(float(random.randrange(1900, 2300, 1))/1000)
            logging.info('len(medias) so far: {}'.format(len(medias)))
        return medias  #TODO test counter and len(media) placement

    # MOVIE SEARCH SECTION
    logging.info('HULU MOVIE SEARCH')
    driver.get('https://www.hulu.com/movies/genres')
    time.sleep(1.5)
    all_genre = driver.find_element_by_id('all_movies_genres')
    anchors = all_genre.find_elements_by_class_name('beacon-click')
    genre_pages = [a.get_attribute('href') for a in anchors]
    logging.info('hulu, got movie genres')
    medias = get_medias_from_genre_pages(genre_pages)
    lookup_and_write_medias(medias, mtype='movie', source=source)

    # SHOW SEARCH SECTION
    logging.info('HULU SHOW SEARCH')
    driver.get('https://www.hulu.com/tv/genres')
    time.sleep(1.5)
    all_genre = driver.find_element_by_id('all_tv_genres')
    anchors = all_genre.find_elements_by_class_name('beacon-click')
    genre_pages = [a.get_attribute('href') for a in anchors]
    logging.info('hulu, got tv genres')
    medias = get_medias_from_genre_pages(genre_pages)
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
    inputs[0].send_keys(creds['nf_u'])
    inputs[1].send_keys(creds['nf_p'])
    driver.find_element_by_tag_name('button').click()
    logging.info('netflix, logged in')

    def get_medias_from_genre_pages(genre_pages):
        medias = []
        for page in genre_pages:
            # get page and scroll to bottom many times
            time.sleep(1.5)
            driver.get(page)
            logging.info('did get on page: {}'.format(page))
            for i in range(40):
                driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(float(random.randrange(900, 1400, 1))/1000)

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
            logging.info('len(medias) so far: {}'.format(len(medias)))
        return medias

    # MOVIE SEARCH SECTION
    logging.info('NETFLIX MOVIE SEARCH')
    genre_pages = [
                   'https://www.netflix.com/browse/genre/5977',  # gay
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
                   'https://www.netflix.com/browse/genre/78367',  # internat'l
                   'https://www.netflix.com/browse/genre/8883',  # romance
                   'https://www.netflix.com/browse/genre/1492',  # scifi
                   'https://www.netflix.com/browse/genre/8933'  # thrillers
                  ]
    medias = get_medias_from_genre_pages(genre_pages)
    lookup_and_write_medias(medias, mtype='movie', source=source)

    # SHOW SEARCH SECTION
    logging.info('NETFLIX SHOW SEARCH')
    genre_pages = ['https://www.netflix.com/browse/genre/83']  # tv ~1500
    medias = get_medias_from_genre_pages(genre_pages)
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
    logging.info('SHOWTIME MOVIE SEARCH')
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
        logging.info('did get on page: {}'.format(link))
        soup = BeautifulSoup(r.text, 'html.parser')

        anchors = soup.find_all('a', {'class': 'movies-gallery__item'})
        for a in anchors:
            title = a['data-label']
            title = title[title.find(':')+1:]
            link = base_url + a['href']
            catalog += [{'title': title, 'link': link}]
    logging.info('will now check avail on {} catalog items'.format(
                 len(catalog)))

    # check availability via link, build medias list
    medias = []
    for c in enumerate(catalog):
        time.sleep(0.100)
        r = requests.get(c[1]['link'])
        soup = BeautifulSoup(r.text, 'html.parser')
        if soup.find(text='STREAM THIS MOVIE'):
            medias += [c[1]]
        if c[0] and c[0] % 50 == 0:
            logging.info(u'checked availability on {} items'.format(c[0]))

    lookup_and_write_medias(medias, mtype='movie', source=source)

    # SHOW SEARCH SECTION
    logging.info('SHOWTIME SHOW SEARCH')
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
    logging.info('HBO MOVIE SEARCH')
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
        catalog = [{'title': m['title'],
                    'link': '{}/{}'.format(base_url, m['link'])}
                   for m in movies if m['link']]
        logging.info('will now check avail on {} catalog items'.format(
             len(catalog)))

        # check availability via movie link, build medias list
        medias = []
        for c in enumerate(catalog):
            r = requests.get(c[1]['link'])
            soup = BeautifulSoup(r.text, 'html.parser')
            if soup.find(text='NOW & GO'):
                medias += [c[1]]
            if c[0] and c[0] % 50 == 0:
                logging.info(u'checked availability on {} items'.format(c[0]))

        lookup_and_write_medias(medias, mtype='movie', source=source)

    # SHOW SEARCH SECTION
    logging.info('HBO SHOW SEARCH')
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
    logging.info('will now check avail on {} catalog items'.format(
         len(catalog)))

    # check availability via link, build medias list
    medias = []
    for c in enumerate(catalog):
        r = requests.get(c[1]['link'])
        soup = BeautifulSoup(r.text, 'html.parser')
        if soup.find(text='NOW & GO'):
            medias += [c[1]]
        if c[0] and c[0] % 50 == 0:
            logging.info(u'checked availability on {} items'.format(c[0]))

    lookup_and_write_medias(medias, mtype='show', source=source)


def lookup_and_write_medias(medias, mtype, source):
    # get unique: list of dict into list of tuples, set, back to dict
    logging.info('len(medias) before take unique: {}'.format(len(medias)))
    medias = [dict(t) for t in set([tuple(d.items()) for d in medias])]
    logging.info('len(medias) after take unique: {}'.format(len(medias)))

    for m in medias:
        source_to_write = dict(source)

        # if media link exists, set source link, try link db lookup / update
        if 'link' in m.keys():
            source_to_write['link'] = m['link']
            full_media = flaskapp.db_lookup_via_link(m['link'])
            if full_media:
                logging.info(u'media link found in db: {}'.format(m['title']))
                flaskapp.update_media_with_source(full_media, source_to_write)
                continue

        # link url was not in database, therefore do themoviedb search
        time.sleep(0.2)
        results = flaskapp.themoviedb_search(m['title'], mtype)

        # exit iteration if search not complete or no results
        if 'total_results' not in results:
            logging.error(u'tmdb search not complete for {}: {}'.format(
                          mtype, m['title']))
            continue
        if results['total_results'] < 1:
            logging.warning(u'tmdb 0 results for {}: {}'.format(
                            mtype, m['title']))
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
        # logging.info(u'tmdb found {}: {}'.format(mtype, full_media['title']))

        # check if titles are not exact match, in future may not append these
        t1 = m['title'].translate({ord(c): None for c in "'’:"})
        t1 = t1.lower().replace('&', 'and')
        t2 = full_media['title'].translate({ord(c): None for c in "'’:"})
        t2 = t2.lower().replace('&', 'and')
        if t1 != t2:
            logging.warning(u'not exact titles: {} | {}'.format(
                            m['title'], full_media['title']))

        # write db media if new
        flaskapp.insert_media_if_new(full_media)

        # update db media with source
        flaskapp.update_media_with_source(full_media, source_to_write)


'''
=amz searches and issues with multiple approaches:=
"Clear and Present Danger 1994" = no result, amz moviepage year=null |
     "Gang ~NY 2002" none amz has 2003 (yr diff)
"Benjamin Button" the result has year=2009, but amz moviepage year=2008
    (as does tmdb), amz only gives rel date that changes
"Snowden" the result has year=2007, diff product than 2016 movie, false pos
    unless compare year
"Snowden 2016", no match (good)
"Deadpool 2016" response is "~Clip: Drawing Deadpool", suggests to compare
    exact titles
"Zoolander 2" response is "Zoolander No. 2: The Magnum Edition", suggests
    to not compare exact titles
"The Terminator 1984", top result is "Terminator Genisys"
Title | Keyword director search fixes all above, adds some issues but
    seem not as big:
-"Creed | Ryan Coogler" has a documentary about the movie as top result
    w/ no year, false neg
-"The Age of Adaline | Lee Toland Krieger" has no results since director
    not returned by amz, false neg
-misspelled dir names, fasle negs: "Contract Killer" jet lei, "Terminator
    Genisys", "Maya the Bee Movie"
'''


if __name__ == "__main__":
    main()
