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

        movies = hbo.get_medias_from_page('/movies', mtype='movie', limit=True)
        self.assertTrue(len(movies) > 50)
        shows = hbo.get_medias_from_page('/series', mtype='show', limit=True)
        self.assertTrue(len(shows) > 50)

        hbo.stop_driver()

if __name__ == "__main__":
    unittest.main()
