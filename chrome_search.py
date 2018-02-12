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
            logging.info('getting year for all media not in database')
            for m in medias:
                if not flaskapp.db_lookup_via_link(m['link']):
                    self.driver.get(m['link'])
                    sleep(randint(5,10))
                    texts = self.driver.find_element_by_tag_name("body").text
                    texts = texts.split('\n')

                    years = [t for t in texts if re.search('^\d{4}.+min$', t)]
                    if len(years) > 0:
                        m['year'] = years[0][:4]
                    logging.info('year lookup: {}: {}'.format(m['title'],
                                                              m.get('year', '')))

            self.lookup_and_write_medias(medias, mtype=page['mtype'], source=source)
        self.stop_driver()

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
