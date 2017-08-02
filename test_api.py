# test_api.py
import unittest
import requests
import json
import flaskapp

class MediaSearchApiTestCase(unittest.TestCase):
    '''This class represents the api test case and will run each test_* func'''

    def setUp(self):  # runs before every 'test_' function
        self.base_url = 'http://media.awctech.com:8181'
        self.app = flaskapp.app.test_client()

    #def tearDown(self):  # runs after every 'test_' function
        # attempt to remove this watchlist item from the database

    def login(self, email, password):
        return self.app.post('/login', data=dict(
            email=email,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    def test_login_logout(self):
        rv = self.login('bad_email@ex.com', '123')
        self.assertTrue('Email not found' in rv.data)
        rv = self.login('dale@coop.com', 'bad_password')
        self.assertTrue('Invalid login' in rv.data)
        #rv = self.login('dale@coop.com', '123')
        #self.assertTrue('You are now logged in' in rv.data)
        # TODO fix: on load of /watchlist, the GET done to display media
        # has connection refused, think related to test_client instance


    def test_get_media_by_id(self):
        rv = self.app.get('/api/show/1920')
        data = json.loads(json.loads(rv.data))  # TODO stop returning '"{}"'
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(data['title'], 'Twin Peaks')
        # TODO write tests for media POST and PUTx2 after written in API


    def test_get_user(self):
        rv = self.login('dale@coop.com', '123')  # throws error, but login ok
        rv = self.app.get('/api/user')
        data = json.loads(json.loads(rv.data))
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(data['email'], 'dale@coop.com')

    '''
    def test_create_user(self):
        data = {'name': 'Imma Newuser',
                'email': 'imma@newuser.com',
                'password': 'this_would_be_a_hash',
                'watchlist': []}
        rv = self.app.post('/api/user', data)
        data = json.loads(json.loads(rv.data))
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(data['email'], 'imma@newuser.com')


    def test_get_watchlist(self):
        # TODO execute login when working from unittest
        # possible to use /api/user and get watchlist like that
        rv = self.app.get('/api/watchlist')
        data = json.loads(json.loads(rv.data))
        self.assertEqual(rv.status_code, 200)
        self.assertTrue(1920 in [i['id'] for i in data if i['mtype'] == 'show'])


    def test_add_to_watchlist(self):
        # TODO execute login when working from unittest
        wl_item = {'id': 10428,
                   'mtype': 'movie',
                   'title': 'Hackers',
                   'year': '1995'}
        rv = self.app.post('/api/watchlist', data)
        data = json.loads(json.loads(rv.data))
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(data['title'], 'Hackers')
        

    def test_delete_from_watchlist(self):
        # TODO execute login when working from unittest
        # TODO add Hackers to watchlist
        data = {'id': 10428}
        rv = self.app.delete('/api/watchlist', data)
        data = json.loads(json.loads(rv.data))
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(data['title'], 'Hackers')
    '''

if __name__ == '__main__':
    unittest.main()
