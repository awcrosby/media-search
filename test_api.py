#!/usr/bin/env python
# -*- coding: utf-8 -*-
# test_api.py

import unittest
import json
import flaskapp


class MediaSearchApiTestCase(unittest.TestCase):
    '''This class represents the api test case and will run each test_* func'''

    def setUp(self):  # runs before every 'test_' function
        self.baseurl = 'http://media.awctech.com:8181'
        self.app = flaskapp.app.test_client()

    # def tearDown(self):  # runs after every 'test_' function

    def login(self, email, password):
        return self.app.post('/login', data=dict(
            email=email,
            password=password
        ), follow_redirects=False)

    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    def test_login_logout(self):
        rv = self.login('bad_email@ex.com', '123')
        self.assertTrue('Email not found' in bytes.decode(rv.data))
        rv = self.login('dale@coop.com', 'bad_password')
        self.assertTrue('Invalid login' in bytes.decode(rv.data))
        rv = self.login('dale@coop.com', '123')
        self.assertTrue('target URL: <a href="/watchlist">' in
                        bytes.decode(rv.data))

    def test_user_search(self):
        rv = self.app.get(self.baseurl + '/search?q=terminator&mtype=all')
        self.assertEqual(rv.status_code, 200)
        self.assertTrue('Search results for' in bytes.decode(rv.data))
        rv = self.app.get(self.baseurl + '/search?q=asdf2847asdf&mtype=all')
        self.assertEqual(rv.status_code, 200)
        self.assertTrue('did not match any results' in bytes.decode(rv.data))
        rv = self.app.get(self.baseurl + '/search?q=broad+city&mtype=show')
        self.assertEqual(rv.status_code, 302)  # redirect to mediainfo.html
        rv = self.app.get(self.baseurl + '/search?q=Ӕon+Flux&mtype=all')
        self.assertEqual(rv.status_code, 302)  # redirect to mediainfo.html

    def test_get_watchlist(self):
        # note this is not used by flaskapp.py or client
        rv = self.login('dale@coop.com', '123')
        rv = self.app.get('/api/watchlist')
        self.assertEqual(rv.status_code, 200)
        json_data = json.loads(bytes.decode(rv.data))
        self.assertTrue(1920 in [i['id'] for i in json_data])

    def test_add_to_watchlist(self):
        rv = self.login('dale@coop.com', '123')
        wl_item = {'id': 10428,
                   'mtype': 'movie',
                   'title': 'Hackers',
                   'year': '1995'}
        rv = self.app.post('/api/watchlist', data=wl_item)

        # since post redirects and not return json, test via get
        rv = self.app.get('/api/watchlist')
        json_data = json.loads(bytes.decode(rv.data))
        self.assertTrue(10428 in [i['id'] for i in json_data])

    def test_delete_from_watchlist(self):
        # add and check it is in watchlist
        rv = self.login('dale@coop.com', '123')
        wl_item = {'id': 10428,
                   'mtype': 'movie',
                   'title': 'Hackers',
                   'year': '1995'}
        rv = self.app.post('/api/watchlist', data=wl_item)
        rv = self.app.get('/api/watchlist')
        json_data = json.loads(bytes.decode(rv.data))
        self.assertTrue(10428 in [i['id'] for i in json_data])

        # delete and check deleted
        rv = self.app.get('/watchlist/delete/movie/10428')
        rv = self.app.get('/api/watchlist')
        json_data = json.loads(bytes.decode(rv.data))
        self.assertFalse(10428 in [i['id'] for i in json_data])


if __name__ == '__main__':
    unittest.main()
