#!/bin/python
# -*- coding: utf-8 -*-

"""This module searches providers of streaming media

Chrome Driver Setup Notes:
    install google chrome in ubuntu: https://askubuntu.com/questions/510056/how-to-install-google-chrome
    chromedriver docs for quickstart: https://sites.google.com/a/chromium.org/chromedriver/getting-started
    set options for headless: https://stackoverflow.com/questions/46920243/
    start display before chrome: https://stackoverflow.com/questions/22424737/

Amazon searches and issues with multiple approaches:
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
"""

from time import sleep
from random import randint
from selenium import webdriver
from pyvirtualdisplay import Display
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (NoSuchElementException, StaleElementReferenceException)
import logging
import re
import flaskapp  # for db lookups/writes and logging
import json
import requests
from bs4 import BeautifulSoup

CHROMEDRIVER_PATH = '/var/chromedriver/chromedriver'

class Scraper():
    def __init__(self):
        with open('creds.json', 'r') as f:
            self.creds = json.loads(f.read())

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

    def lookup_and_write_medias(self, medias, mtype):
        # get unique: list of dict into list of tuples, set, back to dict
        logging.info('len(medias) before take unique: {}'.format(len(medias)))
        medias = [dict(t) for t in set([tuple(d.items()) for d in medias])]
        logging.info('len(medias) after take unique: {}'.format(len(medias)))

        for m in medias:
            source_to_write = dict(self.source)

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

class ShoScraper(Scraper):
    def __init__(self):
        self.base_url = 'http://www.sho.com'
        self.source = {'name': 'showtime',
                       'display_name': 'Showtime',
                       'link': self.base_url}
        self.movie_pages, self.movies, self.shows = [], [] , []

    def get_movie_pages(self):
        r = requests.get(self.base_url + '/movies')
        soup = BeautifulSoup(r.text, 'html.parser')

        # get first movie page for each genre
        full_mov_lib = soup.find('section', {'data-context': 'slider:genres'})
        movie_pages = full_mov_lib.find_all('a', {'class': 'promo__link'})
        movie_pages = [a['href'] for a in movie_pages]
        movie_pages = [i for i in movie_pages if 'adult' not in i]

        # for each first movie page genre, add extra pagination
        all_extra_pages = []
        for page in movie_pages:
            r = requests.get(self.base_url + page)
            soup = BeautifulSoup(r.text, 'html.parser')
            extra_pages = soup.find('ul', 'pagination__list')
            if extra_pages:
                extra_pages = extra_pages.find_all('a')
                extra_pages = [a['href'] for a in extra_pages]
                all_extra_pages.extend(extra_pages)
        movie_pages.extend(all_extra_pages)
        self.movie_pages = movie_pages

    def get_movies(self, limit=None):
        # get catalog which includes movies not streamable
        catalog = []
        for page in self.movie_pages:
            r = requests.get(self.base_url + page)
            logging.info('did get on page: {}'.format(page))
            soup = BeautifulSoup(r.text, 'html.parser')

            anchors = soup.find_all('a', {'class': 'movies-gallery__item'})
            for a in anchors:
                title = a['data-label']
                title = title[title.find(':')+1:]
                catalog += [{'title': title, 'link': self.base_url + a['href']}]
        logging.info('will now check avail on {} catalog items'.format(
                     len(catalog)))

        # check catalog for streamable movies, clear and build movies list
        self.movies = []
        for i, c in enumerate(catalog):
            sleep(0.25)
            r = requests.get(c['link'])
            soup = BeautifulSoup(r.text, 'html.parser')

            year = soup.find_all('dd')[-1].text
            if year and re.search('^\d{4}$', year):
                c['year'] = year
            if soup.find(text='STREAM THIS MOVIE'):
                self.movies += [c]
            if i % 100 == 0:
                logging.info(u'checked availability on {} items'.format(i))
            if limit and (i >= limit-1):  # used for unit testing
                break

    def get_shows(self):
        r = requests.get(self.base_url + '/series')
        soup = BeautifulSoup(r.text, 'html.parser')
        all_series = soup.find('section',
                         {'data-context': 'promo group:All Showtime Series'})

        self.shows = []
        anchors = all_series.find_all('a', {'class': 'promo__link'})
        for a in anchors:
            title = a.text.strip()
            link = self.base_url + a['href']
            self.shows += [{'title': title, 'link': link}]

    def scrape_and_write_medias(self):
        """Searches showtime for media, uses lighter requests/bs4 not chrome"""
        logging.info('SHOWTIME MOVIE SEARCH')
        self.get_movie_pages()
        self.get_movies()
        self.lookup_and_write_medias(medias=self.movies, mtype='movie')

        logging.info('SHOWTIME SHOW SEARCH')
        self.get_shows()
        self.lookup_and_write_medias(medias=self.shows, mtype='show')

        # remove any sources not just updated: media this provider no longer has
        flaskapp.remove_old_sources('showtime')


class HboScraper(Scraper):
    def __init__(self):
        self.base_url = 'https://play.hbogo.com'
        self.source = {'name': 'hbo',
                       'display_name': 'HBO',
                       'link': self.base_url}

    def get_medias_from_page(self, page, mtype, limit=None):
        medias = []
        logging.info('getting page: {}'.format(page))
        self.driver.get(self.base_url + page)
        for scroll in range(4):
            # get all boxes with media image and text
            sleep(10)
            boxes = self.driver.find_elements_by_xpath("//a[@class='default class2 class4']")
            logging.info('boxes found: {}'.format(len(boxes)))

            # create list of titles and links, replacing newline
            for i, box in enumerate(boxes):
                title = box.text.replace('\n', ' ')
                medias += [{'title': title, 'link': box.get_attribute('href')}]
            logging.info('num of medias so far: {}'.format(len(medias)))

            # scroll down to have more boxes visible
            self.driver.execute_script("window.scrollBy(0, 6000);")
            if limit:  # exits quickly for unit test
                break

        # get unique medias
        medias = [dict(t) for t in set([tuple(d.items()) for d in medias])]
        logging.info('post-unique, num of medias: {}'.format(len(medias)))

        # self.driver.save_screenshot('static/screenshot.png')  ## if memory

        # remove non-media
        medias = [m for m in medias if 'scrollReset' not in m['link']]
        logging.info('post-cleanup, num medias: {}'.format(len(medias)))
        return medias

    def add_years_to_movies(self, movies):
        logging.info('getting year for movies if not in database')
        for m in movies:
            if not flaskapp.db_lookup_via_link(m['link']):
                self.driver.get(m['link'])
                sleep(randint(5,10))
                texts = self.driver.find_element_by_tag_name("body").text
                texts = texts.split('\n')

                years = [t for t in texts if re.search('^\d{4}.+min$', t)]
                if len(years) > 0:
                    m['year'] = years[0][:4]
                logging.info('year lookup: {}: {}'.format(m['title'], m.get('year', '')))
        return movies

    def scrape_and_write_medias(self):
        self.start_driver(window_size='--window-size=1920,6000')

        logging.info('HBO MOVIE SEARCH')
        movies = self.get_medias_from_page('/movies', mtype='movie')
        movies = self.add_years_to_movies(movies)
        self.lookup_and_write_medias(medias=movies, mtype='movie')

        logging.info('HBO SHOW SEARCH')
        shows = self.get_medias_from_page('/series', mtype='show')
        self.lookup_and_write_medias(medias=shows, mtype='show')

        self.stop_driver()
        # remove any sources not just updated: media this provider no longer has
        flaskapp.remove_old_sources('hbo')

class ProviderSearch():
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
            medias = []
            for scroll in range(4):
                # get all boxes with media image and text
                sleep(15)
                boxes = self.driver.find_elements_by_xpath("//a[@class='default class2 class4']")
                logging.info('boxes found: {}'.format(len(boxes)))

                # create list of titles and links, replacing newline
                for i, b in enumerate(boxes):
                    title = b.text.replace('\n', ' ')
                    medias += [{'title': title, 'link': b.get_attribute('href')}]
                logging.info('num of medias so far: {}'.format(len(medias)))

                # scroll down to have more boxes visible
                self.driver.execute_script("window.scrollBy(0, 6000);")

            # get unique medias
            medias = [dict(t) for t in set([tuple(d.items()) for d in medias])]
            logging.info('post-unique, num of medias: {}'.format(len(medias)))

            # self.driver.save_screenshot('static/screenshot.png')  ## if mem

            # remove non-media
            medias = [m for m in medias if 'feature' in m['link']]
            logging.info('post-cleanup, num medias: {}'.format(len(medias)))

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

    def search_netflix(self):
        """Searches netflix for media"""

        def get_medias_from_genre_pages(genre_pages):
            medias = []
            for page in genre_pages:
                sleep(1.5)
                self.driver.get(page + '?so=su')
                logging.info('did get on page: {}'.format(page))
                for i in range(40):  # scroll to bottom many times
                    self.driver.execute_script(
                        "window.scrollTo(0, document.body.scrollHeight);")
                    sleep(randint(1,2))

                divs = self.driver.find_elements_by_xpath("//div[contains(@class, 'ptrack-content')]")
                #import pdb; pdb.set_trace()
                for d in divs:
                    title = d.find_element_by_css_selector('div.video-preload-title-label').text
                    elements = d.get_attribute('data-ui-tracking-context').split(',')
                    vid_element = [i for i in elements if 'video_id' in i]
                    netflix_id = vid_element[0][vid_element[0].find(':')+1:]
                    link = base_url+'/title/'+netflix_id
                    medias += [{'title': title, 'link': link}]
                logging.info('len(medias) so far: {}'.format(len(medias)))
            return medias

        def get_netflix_year(medias):
            # netflix show year is recent not first air year, cant use in tmdb search
            medias = [dict(t) for t in set([tuple(d.items()) for d in medias])]
            logging.info('unique medias in get_netflix_year(): {}'.format(len(medias)))
            self.start_driver()

            count = 0
            for i, media in enumerate(medias):
                if count >= 190:
                    logging.error('Exiting get_netflix_year early via counter')
                    break
                if 'link' in media.keys() and not flaskapp.db_lookup_via_link(media['link']):
                    sleep(randint(20,30))
                    try:  # only for new media not in database
                        count += 1
                        self.driver.get(media['link'])
                        year = self.driver.find_element_by_xpath("//span[@class='year']").text
                        media['year'] = year
                        logging.info('Media #{}, YEAR LOOKUP #{}: {}'.format(i, count, media))
                    except:
                        pass
            return medias


        logging.info('starting netflix search')
        self.start_driver()
        base_url = 'http://www.netflix.com'
        source = {'name': 'netflix', 'display_name': 'Netflix', 'link': base_url}

        # log in to provider
        self.driver.get('https://www.netflix.com/login')
        inputs = self.driver.find_elements_by_tag_name('input')
        inputs[0].send_keys(self.creds['nf_u'])
        inputs[1].send_keys(self.creds['nf_p'])
        self.driver.find_element_by_tag_name('button').click()
        logging.info('netflix, logged in')

        # SHOW SEARCH SECTION
        logging.info('NETFLIX SHOW SEARCH')
        genre_pages = [
                       'https://www.netflix.com/browse/genre/83',  # tv popular
                       'https://www.netflix.com/browse/genre/10673',  # action
                       'https://www.netflix.com/browse/genre/10375',  # com
                       'https://www.netflix.com/browse/genre/11714',  # drama
                       'https://www.netflix.com/browse/genre/83059',  # horror
                       'https://www.netflix.com/browse/genre/4366',  # mystery
                       'https://www.netflix.com/browse/genre/52780',  # sci
                       'https://www.netflix.com/browse/genre/4814',  # miniseries
                       'https://www.netflix.com/browse/genre/46553'  # classic
                      ]
        medias = get_medias_from_genre_pages(genre_pages)
        self.lookup_and_write_medias(medias, mtype='show', source=source)

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
        self.stop_driver()  # get_netflix_year() will start a new driver
        medias = get_netflix_year(medias)
        self.lookup_and_write_medias(medias, mtype='movie', source=source)

        # remove any sources not just updated: media this provider no longer has
        flaskapp.remove_old_sources('netflix')

    def search_hulu(self):
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
                top_panel = self.driver.find_element_by_class_name('tray')
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
        form.find_element_by_name('email').send_keys(self.creds['hulu_u'])
        form.find_element_by_name('password').send_keys(self.creds['hulu_p'])
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
        all_genre = self.driver.find_element_by_id('all_movies_genres')
        anchors = all_genre.find_elements_by_class_name('beacon-click')
        genre_pages = [a.get_attribute('href') for a in anchors]
        logging.info('hulu, got movie genres')
        medias = get_medias_from_genre_pages(genre_pages)
        self.lookup_and_write_medias(medias, mtype='movie', source=source)

        # SHOW SEARCH SECTION
        logging.info('HULU SHOW SEARCH')
        self.driver.get('https://www.hulu.com/tv/genres')
        sleep(1.5)
        all_genre = self.driver.find_element_by_id('all_tv_genres')
        anchors = all_genre.find_elements_by_class_name('beacon-click')
        genre_pages = [a.get_attribute('href') for a in anchors]
        logging.info('hulu, got tv genres')
        medias = get_medias_from_genre_pages(genre_pages)
        self.lookup_and_write_medias(medias, mtype='show', source=source)

        self.stop_driver()
        flaskapp.remove_old_sources('hulu')  # remove sources not just updated

    def update_watchlist_amz(self):
        """for watchlist items check if amz is a source and add to db"""
        wl_unique = flaskapp.get_all_watchlist_in_db()
        for m in wl_unique:
            media = flaskapp.themoviedb_lookup(m['mtype'], m['id'])
            flaskapp.amz_prime_check(media)
            sleep(2.5)
            flaskapp.amz_pay_check(media)
            sleep(2.5)

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


def main():
    #bot = ShoScraper()
    #bot.scrape_and_write_medias()

    bot = HboScraper()
    bot.scrape_and_write_medias()

    #bot.search_netflix()
    #bot.search_hulu()
    #bot.search_showtime()
    #bot.search_hbo()
    #bot.update_watchlist_amz()
    #flaskapp.remove_hulu_addon_media()
    #flaskapp.reindex_database()


if __name__ == "__main__":
    main()
