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
    """Scraper parent class, child classes are media streaming sites."""
    def __init__(self):
        """Sets creds for each instance."""
        with open('creds.json', 'r') as f:
            self.creds = json.loads(f.read())

    def start_driver(self, window_size='--window-size=1920,1080'):
        """Starts headless chrome browser/driver."""
        logging.info('starting driver')
        self.display = Display(visible=0)
        # self.display = Display(visible=0, size=(1920, 1080))
        self.display.start()

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')  # likely necessary
        options.add_argument(window_size)
        self.driver = webdriver.Chrome(CHROMEDRIVER_PATH, options=options)
        self.driver.implicitly_wait(10)  # seconds

    def stop_driver(self):
        """Stops headless browser/driver."""
        logging.info('stopping driver')
        self.display.stop()
        self.driver.quit()

    def lookup_and_write_medias(self, medias, mtype):
        """Takes list of movies or shows, searches themoviedb,
           creates object to write to database, then inserts if new
           or updates timestamp if not new.
        """
        logging.info('len(medias) before take unique: {}'.format(len(medias)))
        # get unique: list of dict into list of tuples, set, back to dict
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

    def update_watchlist_amz(self):
        """For watchlist items check if amazon prime and amazon pay
           are sources and add to db"""
        wl_unique = flaskapp.get_all_watchlist_in_db()
        for m in wl_unique:
            media = flaskapp.themoviedb_lookup(m['mtype'], m['id'])
            flaskapp.amz_prime_check(media)
            sleep(2.5)
            flaskapp.amz_pay_check(media)
            sleep(2.5)


class ShoScraper(Scraper):
    def __init__(self):
        """Sets class variables, including data that is scraped."""
        self.base_url = 'http://www.sho.com'
        self.source = {'name': 'showtime',
                       'display_name': 'Showtime',
                       'link': self.base_url}
        self.movie_pages, self.movies, self.shows = [], [], []

    def get_movie_pages(self):
        """Get list of web pages that contain movies."""
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
        """Get movies list from class variable movie_pages."""
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

        catalog = [dict(t) for t in set([tuple(d.items()) for d in catalog])]
        logging.info('will now check avail on {} catalog items'.format(
                     len(catalog)))

        # check catalog for streamable movies, clear and build movies list
        self.movies = []
        for i, c in enumerate(catalog):
            sleep(0.3)
            r = requests.get(c['link'])
            soup = BeautifulSoup(r.text, 'html.parser')

            year = soup.find_all('dd')[-1].text
            if year and re.search(r'^\d{4}$', year):
                c['year'] = year
            if soup.find(text='STREAM THIS MOVIE'):
                self.movies += [c]
            if i % 100 == 0:
                logging.info(u'checked availability on {} items'.format(i))
            if limit and (i >= limit-1):  # used for unit testing
                break

    def get_shows(self):
        """Get shows list from class variable show_pages."""
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
        """Gets movies and shows and writes to database.
           ShoScraper uses lighter requests/bs4 not selenium/chromedriver.
        """
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
        """Sets class variables."""
        self.base_url = 'https://play.hbogo.com'
        self.source = {'name': 'hbo',
                       'display_name': 'HBO',
                       'link': self.base_url}

    def get_medias_from_page(self, page, mtype, limit=None):
        """Get medias list for given page."""
        medias = []
        logging.info('getting page: {}'.format(page))
        self.driver.get(self.base_url + page)
        scrolls = 4 if mtype == 'movie' else 1
        for scroll in range(scrolls):
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
        """Get year for each movie dict in movies list,
           if movie not already in database
        """
        logging.info('getting year for movies if not in database')
        for m in movies:
            if not flaskapp.db_lookup_via_link(m['link']):
                self.driver.get(m['link'])
                sleep(randint(5, 10))
                texts = self.driver.find_element_by_tag_name("body").text
                texts = texts.split('\n')

                years = [t for t in texts if re.search(r'^\d{4}.+min$', t)]
                if len(years) > 0:
                    m['year'] = years[0][:4]
                logging.info('year lookup: {}: {}'.format(m['title'], m.get('year', '')))
        return movies

    def scrape_and_write_medias(self):
        """Gets movies and shows and writes to database."""
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


class NetflixScraper(Scraper):
    def __init__(self):
        """Runs parent __init__ and sets class variables."""
        super(NetflixScraper, self).__init__()
        self.base_url = 'http://www.netflix.com'
        self.source = {'name': 'netflix',
                       'display_name': 'Netflix',
                       'link': self.base_url}

        self.movie_genre_pages = [
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

        self.show_genre_pages = [
            'https://www.netflix.com/browse/genre/83',  # tv popular
            'https://www.netflix.com/browse/genre/10673',  # action
            'https://www.netflix.com/browse/genre/10375',  # com
            'https://www.netflix.com/browse/genre/11714',  # drama
            'https://www.netflix.com/browse/genre/83059',  # horror
            'https://www.netflix.com/browse/genre/4366',  # mystery
            'https://www.netflix.com/browse/genre/52780',  # sci
            'https://www.netflix.com/browse/genre/4814',  # miniseries
            'https://www.netflix.com/browse/genre/46553',  # classic
        ]

    def login(self):
        """Logs in to site, returns true if logged in."""
        self.driver.get(self.base_url + '/login')
        inputs = self.driver.find_elements_by_tag_name('input')
        inputs[0].send_keys(self.creds['nf_u'])
        inputs[1].send_keys(self.creds['nf_p'])
        self.driver.find_element_by_tag_name('button').click()

        if self.driver.current_url == 'https://www.netflix.com/browse':
            return True
        return False

    def get_medias(self, mtype, limit=None):
        """Gets movies or shows, uses class variable for genre_pages."""
        if mtype == 'movie':
            genre_pages = self.movie_genre_pages
        elif mtype == 'show':
            genre_pages = self.show_genre_pages

        medias = []
        for page in genre_pages:
            sleep(1.5)
            self.driver.get(page + '?so=su')
            logging.info('did get on page: {}'.format(page))
            for scroll in range(40):  # scroll to bottom many times
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);")
                sleep(randint(1, 2))
                if limit:  # exit early for unit test
                    break

            divs = self.driver.find_elements_by_xpath("//div[contains(@class, 'ptrack-content')]")
            for d in divs:
                try:
                    # import pdb; pdb.set_trace()
                    title = d.text
                    elements = d.get_attribute('data-ui-tracking-context').split(',')
                    vid_element = [i for i in elements if 'video_id' in i]
                    netflix_id = vid_element[0][vid_element[0].find(':')+1:]
                    link = self.base_url + '/title/' + netflix_id
                    medias += [{'title': title, 'link': link}]
                except NoSuchElementException:
                    logging.warning('no title found in netflix {}'.format(mtype))
                except IndexError:
                    logging.warning('no link found in netflix for title: {}'.format(title))
            logging.info('len(medias) so far: {}'.format(len(medias)))
            if limit:  # exit early for unit test
                break
        return medias

    def add_years_to_movies(self, movies):
        """Get year for each movie dict in movies list,
           if movie not already in database.

           Netflix show year is recent not first air year,
           so can't  use in tmdb search
        """
        logging.info('getting year for movies if not in database')
        movies = [dict(t) for t in set([tuple(d.items()) for d in movies])]
        logging.info('unique movies count: {}'.format(len(movies)))

        count = 0
        for i, movie in enumerate(movies):
            if 'link' in movie.keys() and not flaskapp.db_lookup_via_link(movie['link']):
                sleep(randint(10, 15))
                try:
                    count += 1
                    self.driver.get(movie['link'])
                    year = self.driver.find_element_by_xpath("//span[@class='year']").text
                    movie['year'] = year
                    logging.info('Media #{}, YEAR LOOKUP #{}: {}'.format(i, count, movie))
                except:
                    pass
        return movies

    def scrape_and_write_medias(self):
        """Gets movies and shows and writes to database."""
        self.start_driver()
        if self.login():
            logging.info('NETFLIX SHOW SEARCH')
            shows = self.get_medias(mtype='show')
            self.lookup_and_write_medias(medias=shows, mtype='show')

            logging.info('NETFLIX MOVIE SEARCH')
            movies = self.get_medias(mtype='movie')
            # restart driver, effectively logging out, for rate limiting
            self.stop_driver()
            self.start_driver()
            # add years to movies
            movies = self.add_years_to_movies(movies)
            self.lookup_and_write_medias(medias=movies, mtype='movie')

        else:
            logging.error('NETFLIX login failed')

        self.stop_driver()
        # remove any sources not just updated: media this provider no longer has
        flaskapp.remove_old_sources('netflix')


class HuluScraper(Scraper):
    def __init__(self):
        """Runs parent __init__ and sets class variables."""
        super(HuluScraper, self).__init__()
        self.base_url = 'https://www.hulu.com'
        self.source = {'name': 'hulu',
                       'display_name': 'Hulu',
                       'link': self.base_url}

    def login(self):
        """Logs in to site, returns true if logged in."""
        self.driver.get('https://auth.hulu.com/web/login')
        sleep(2)

        form = self.driver.find_element_by_class_name('hulu-login')
        form.find_element_by_name('email').send_keys(self.creds['hulu_u'])
        form.find_element_by_name('password').send_keys(self.creds['hulu_p'])
        # self.driver.save_screenshot('static/screenshot.png')
        # self.driver.find_element_by_id('recaptcha_response_field').send_keys('')
        form.find_element_by_class_name('login-button').click()
        logging.info('hulu, clicked login button')
        sleep(1.2)

        try:  # try 2nd click, sometimes 1st click does not work
            form.find_element_by_class_name('login-button').click()
            sleep(1.2)
        except:
            pass

        self.driver.find_element_by_id('62038018').click()
        logging.info('hulu, clicked profile')
        sleep(1.2)

        if self.driver.current_url == 'https://www.hulu.com/':
            return True
        return False

    def get_genre_pages(self, mtype):
        """Gets genre_pages list for either movies or shows."""
        if mtype == 'movie':
            div_id = 'all_movies_genres'
            url = '/movies/genres'
        else:
            div_id = 'all_tv_genres'
            url = '/tv/genres'

        self.driver.get(self.base_url + url)
        sleep(2)

        genres = self.driver.find_element_by_id(div_id)
        anchors = genres.find_elements_by_class_name('beacon-click')
        genre_pages = [a.get_attribute('href') for a in anchors]
        logging.info('hulu, got genre_pages')

        return genre_pages

    def get_medias(self, genre_pages, limit=None):
        """Gets movies or shows, using method variable for list of genre_pages."""
        medias = []
        for page in genre_pages:
            if page.endswith('latino') or page.endswith('videogames'):
                continue  # says latino movie genre, but shows not movies

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
                    try:  # get movie year, show's year first aired is not displayed
                        year = t.find_element_by_tag_name('img').get_attribute('alt')
                        if re.search(r'\([0-9][0-9][0-9][0-9]\)$', year):
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
                sleep(randint(2, 3))
                if limit:  # exit early for unit test
                    break
            if limit:  # exit early for unit test
                break
            logging.info('len(medias) so far: {}'.format(len(medias)))

        return medias

    def scrape_and_write_medias(self):
        """Gets movies and shows and writes to database."""
        self.start_driver()
        if self.login():
            logging.info('HULU MOVIE SEARCH')
            movie_genre_pages = self.get_genre_pages(mtype='movie')
            movies = self.get_medias(movie_genre_pages)
            self.lookup_and_write_medias(medias=movies, mtype='movie')

            logging.info('HULU SHOW SEARCH')
            show_genre_pages = self.get_genre_pages(mtype='show')
            shows = self.get_medias(show_genre_pages)
            self.lookup_and_write_medias(medias=shows, mtype='show')
        else:
            logging.error('HULU login failed')

        self.stop_driver()
        flaskapp.remove_old_sources('hulu')  # remove sources not just updated
        flaskapp.remove_hulu_addon_media()  # remove overlap of sho and hulu


def main():
    """Executes each subclass of Scraper parent class,
       updates amazon sources for watchlist, reindexes database.
    """
    site_scrapers = [
        ShoScraper(),
        HboScraper(),
        NetflixScraper(),
        HuluScraper(),
    ]
    for scraper in site_scrapers:
        scraper.scrape_and_write_medias()

    parent_scraper = Scraper()
    parent_scraper.update_watchlist_amz()

    flaskapp.reindex_database()


if __name__ == "__main__":
    main()
