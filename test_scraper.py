#! /usr/bin/env python
# -*- coding: utf-8 -*-
# test_scraper.py

import unittest
from scraper import Scraper, ShoScraper, HboScraper

class ScraperTestCase(unittest.TestCase):
    # def setUp(self):
    # def tearDown(self):

    def Xtest_driver_started(self):
        bot = Scraper()
        bot.start_driver()
        bot.driver.current_url  # access attr of driver
        bot.stop_driver()

    def Xtest_showtime_scrape(self):
        sho = ShoScraper()
        sho.get_movie_pages()
        self.assertTrue(len(sho.movie_pages) > 15)
        sho.get_movies(limit=10)
        self.assertTrue(len(sho.movies) > 4)
        sho.get_shows()
        self.assertTrue(len(sho.shows) > 40)

    def test_hbo_scrape(self):
        hbo = HboScraper()
        hbo.start_driver(window_size='--window-size=1920,6000')

        movies = hbo.get_medias_from_page('/movies', mtype='movie', limit=1)
        self.assertTrue(len(movies) > 200)

        #TODO see why shows post-cleanup step goes from 106 to 0
        # test adding year class method
        # run unit tests on prod box to see if any driver issues
        # test removing old sources
        # del all hbo media so will search for years (overall test)

        #shows = hbo.get_medias_from_page('/series', mtype='show', limit=1)
        #self.assertTrue(len(shows) > 20)
        #print('num shows', len(shows))

        hbo.stop_driver()

if __name__ == "__main__":
    unittest.main()
