#! /usr/bin/env python
# -*- coding: utf-8 -*-
# test_scraper.py

import unittest
import warnings
import scraper


class ScraperTestCase(unittest.TestCase):
    def setUp(self):
        # ignore this unclosed socket warning that python usually suppresses
        warnings.simplefilter("ignore", ResourceWarning)

    def test_driver_started(self):
        bot = scraper.Scraper()
        bot.start_driver()
        bot.driver.current_url  # access attr of driver
        bot.stop_driver()

    def test_showtime_scrape(self):
        sho = scraper.ShoScraper()

        sho.get_movie_pages()
        self.assertTrue(len(sho.movie_pages) > 15)
        sho.get_movies(limit=10)
        self.assertTrue(len(sho.movies) > 4)
        sho.get_shows()
        self.assertTrue(len(sho.shows) > 40)

    def test_hbo_scrape(self):
        hbo = scraper.HboScraper()
        hbo.start_driver(window_size='--window-size=1920,6000')

        movies = hbo.get_medias_from_page('/movies', mtype='movie', limit=True)
        self.assertTrue(len(movies) > 50)
        shows = hbo.get_medias_from_page('/series', mtype='show', limit=True)
        self.assertTrue(len(shows) > 50)

        hbo.stop_driver()

    def test_netflix_scrape(self):
        netflix = scraper.NetflixScraper()
        netflix.start_driver()

        self.assertTrue(netflix.login())
        movies = netflix.get_medias(mtype='movie', limit=True)
        self.assertTrue(len(movies) > 20)
        shows = netflix.get_medias(mtype='show', limit=True)
        self.assertTrue(len(shows) > 20)

        netflix.stop_driver()

    def test_hulu_scrape(self):
        hulu = scraper.HuluScraper()
        hulu.start_driver()

        self.assertTrue(hulu.login())

        movie_genre_pages = hulu.get_genre_pages(mtype='movie')
        self.assertTrue(len(movie_genre_pages) > 15)
        movies = hulu.get_medias(movie_genre_pages, limit=True)
        self.assertTrue(len(movies) > 3)

        show_genre_pages = hulu.get_genre_pages(mtype='show')
        self.assertTrue(len(show_genre_pages) > 15)
        shows = hulu.get_medias(show_genre_pages, limit=True)
        self.assertTrue(len(shows) > 3)

        hulu.stop_driver()


if __name__ == "__main__":
    unittest.main()
