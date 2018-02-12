#!/bin/python
# -*- coding: utf-8 -*-

"""
Class to search providers of streaming media

install google chrome in ubuntu: https://askubuntu.com/questions/510056/how-to-install-google-chrome
chromedriver docs for quickstart: https://sites.google.com/a/chromium.org/chromedriver/getting-started
set options for headless: https://stackoverflow.com/questions/46920243/
start display before chrome: https://stackoverflow.com/questions/22424737/

"""

from time import sleep
from random import randint
from selenium import webdriver
from pyvirtualdisplay import Display
from selenium.webdriver.chrome.options import Options
import logging
from bs4 import BeautifulSoup
import re
import flaskapp  # for db lookups/writes and logging

CHROMEDRIVER_PATH = '/var/chromedriver/chromedriver'

class ProviderSearch():
    #def __init__(self):
        #logging.basicConfig(filename='provider_search.log',
        #                    format='%(asctime)s %(levelname)s: %(message)s',
        #                    level=logging.INFO)

    def start_driver(self, window_size='--window-size=1920,1080'):
        """Starts headless chrome browser/driver"""
        logging.info('starting driver')
        self.display = Display(visible=0)
        #self.display = Display(visible=0, size=(1920, 1080))
        self.display.start()

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')  # likely necessary
        options.add_argument(window_size)
        self.driver = webdriver.Chrome(CHROMEDRIVER_PATH, chrome_options=options)
        self.driver.implicitly_wait(10)  # seconds

    def stop_driver(self):
        """Stops headless driver"""
        logging.info('stopping driver')
        self.display.stop()
        self.driver.quit()

    def search_hbo(self):
        """Searches hbo for media"""
        logging.info('starting hbo search')
        self.start_driver(window_size='--window-size=1920,6000')

        base_url = 'https://play.hbogo.com'
        source = {'name': 'hbo', 'display_name': 'HBO', 'link': base_url}
        pages = [{'url': '/movies', 'mtype': 'movie'},
                 {'url': '/series', 'mtype': 'show'},
                 {'url': '/documentaries', 'mtype': 'movie'}]

        for page in pages:
            logging.info('HBO SEARCH OF ' + page['url'])
            self.driver.get(base_url + page['url'])
            sleep(5)
            self.driver.execute_script("window.scrollTo(0, 10000);")  # scroll
            sleep(15)
            #self.driver.save_screenshot('screenshot.png')

            # get all boxes with media image and text
            boxes = self.driver.find_elements_by_xpath("//a[@class='default class2 class4']")
            logging.info('num of media boxes found: {}'.format(len(boxes)))

            # create list of titles and links, replacing newline
            medias = []
            for i, b in enumerate(boxes):
                title = b.text.replace('\n', ' ')
                medias += [{'title': title, 'link': b.get_attribute('href')}]

            # remove non-media, TODO make not catch false positives
            medias = [m for m in medias if not m['title'].isupper()]

            # get year if not already in database
            logging.info('getting year for all movies not in database')
            for m in medias:
                if page['mtype'] == 'movie' and not flaskapp.db_lookup_via_link(m['link']):
                    self.driver.get(m['link'])
                    sleep(randint(5,10))
                    texts = self.driver.find_element_by_tag_name("body").text
                    texts = texts.split('\n')

                    years = [t for t in texts if re.search('^\d{4}.+min$', t)]
                    if len(years) > 0:
                        m['year'] = years[0][:4]
                    logging.info('year lookup: {}: {}'.format(m['title'], m.get('year', '')))

            self.lookup_and_write_medias(medias, mtype=page['mtype'], source=source)
        self.stop_driver()

    def search_hulu():
        """Searches hulu for media"""

        def get_medias_from_genre_pages(genre_pages):
            medias = []
            for page in genre_pages:
                if page == 'https://www.hulu.com/videogames':
                    continue
                if page == 'https://www.hulu.com/latino':
                    continue  # says movie genre but shows not movies
                # get page and pointer to top panel, holding about 6 medias
                self.driver.get(page)
                logging.info('did get on page: {}'.format(page))
                sleep(8)
                top_panel = driver.find_element_by_class_name('tray')
                next_btn = top_panel.find_element_by_class_name('next')
                next_counter = 0

                # get visible media, click next, repeat until no next button
                while True:
                    thumbnails = top_panel.find_elements_by_class_name('row')
                    for t in thumbnails:
                        try:  # get movie year, show first air year not displayed
                            year = t.find_element_by_tag_name('img').get_attribute('alt')
                            if re.search('\([0-9][0-9][0-9][0-9]\)$', year):
                                year = year[-5:-1]
                            else:
                                year = ''
                        except:
                            year = ''
                        try:
                            title = t.find_element_by_class_name('title').get_attribute('innerHTML')
                            link = t.find_element_by_class_name('beacon-click').get_attribute('href')
                            medias += [{'title': title, 'link': link, 'year': year}]
                        except NoSuchElementException:
                            logging.warning('no title in row html, blank grid')
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
                    sleep(randint(2,3))
                logging.info('len(medias) so far: {}'.format(len(medias)))
            return medias

        logging.info('starting hulu search')
        self.start_driver()
        self.driver.get('https://auth.hulu.com/web/login')
        source = {'name': 'hulu', 'display_name': 'Hulu', 'link': 'http://www.hulu.com'}
        sleep(2)

        # enter credentials and click login button
        form = self.driver.find_element_by_tag_name('form')
        form.find_element_by_name('email').send_keys(creds['hulu_u'])
        form.find_element_by_name('password').send_keys(creds['hulu_p'])
        # self.driver.save_screenshot('static/screenshot.png')
        # self.driver.find_element_by_id('recaptcha_response_field').send_keys('')
        form.find_element_by_class_name('login-button').click()
        sleep(1.2)
        try:  # sometimes first click does not work
            form.find_element_by_class_name('login-button').click()
            sleep(1.2)
        except:
            pass
        logging.info('hulu, clicked login button')

        # click profile link
        self.driver.find_element_by_id('62038018').click()
        sleep(1.2)
        logging.info('hulu, clicked profile')

        # MOVIE SEARCH SECTION
        logging.info('HULU MOVIE SEARCH')
        self.driver.get('https://www.hulu.com/movies/genres')
        sleep(1.5)
        all_genre = driver.find_element_by_id('all_movies_genres')
        anchors = all_genre.find_elements_by_class_name('beacon-click')
        genre_pages = [a.get_attribute('href') for a in anchors]
        logging.info('hulu, got movie genres')
        medias = get_medias_from_genre_pages(genre_pages)
        lookup_and_write_medias(medias, mtype='movie', source=source)

        # SHOW SEARCH SECTION
        logging.info('HULU SHOW SEARCH')
        self.driver.get('https://www.hulu.com/tv/genres')
        sleep(1.5)
        all_genre = driver.find_element_by_id('all_tv_genres')
        anchors = all_genre.find_elements_by_class_name('beacon-click')
        genre_pages = [a.get_attribute('href') for a in anchors]
        logging.info('hulu, got tv genres')
        medias = get_medias_from_genre_pages(genre_pages)
        lookup_and_write_medias(medias, mtype='show', source=source)

        self.stop_driver()
        flaskapp.remove_old_sources('hulu')  # remove sources not just updated


    def lookup_and_write_medias(self, medias, mtype, source):
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
                    # logging.info(u'db media link found: {}'.format(m['title']))
                    flaskapp.update_media_with_source(full_media, source_to_write)
                    continue

            # link url was not in database, therefore do themoviedb search
            sleep(0.2)
            year = m.get('year', '')

            results = flaskapp.themoviedb_search(m['title'], mtype, year=year)

            # exit iteration if search not complete or no results
            if 'total_results' not in results:
                logging.error(u'tmdb search not complete for {}: {} {}'.format(
                              mtype, m['title'], year))
                continue
            if results['total_results'] < 1:
                logging.warning(u'tmdb 0 results for {}: {} {}'.format(
                                mtype, m['title'], year))
                # empty media for db write, prevent re-searching
                full_media = dict()
                full_media['title'] = m['title']
                full_media['mtype'] = mtype
                full_media['year'] = year
                full_media['id'] = m['link']
                full_media['sources'] = []
            else:
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

                # check if titles are not exact match, in future may not append these
                if not flaskapp.doTitlesMatch(m['title'], full_media['title']):
                    logging.warning(u'not exact titles: {} | {}'.format(
                                    m['title'], full_media['title']))

            # write db media if new
            flaskapp.insert_media_if_new(full_media)

            # update db media with source
            flaskapp.update_media_with_source(full_media, source_to_write)


Search = ProviderSearch()
Search.search_hbo()
