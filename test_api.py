# test_api.py
import unittest
import json
import flaskapp


class MediaSearchApiTestCase(unittest.TestCase):
    '''This class represents the api test case and will run each test_* func'''

    def setUp(self):  # runs before every 'test_' function
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
        self.assertTrue('Email not found' in rv.data)
        rv = self.login('dale@coop.com', 'bad_password')
        self.assertTrue('Invalid login' in rv.data)
        rv = self.login('dale@coop.com', '123')
        self.assertTrue('target URL: <a href="/watchlist">' in rv.data)

    def test_get_watchlist(self):
        # note this is not used by flaskapp.py or client
        rv = self.login('dale@coop.com', '123')
        rv = self.app.get('/api/watchlist')
        self.assertEqual(rv.status_code, 200)
        self.assertTrue(1920 in [i['id'] for i in json.loads(rv.data)])

    def test_add_to_watchlist(self):
        rv = self.login('dale@coop.com', '123')
        wl_item = {'id': 10428,
                   'mtype': 'movie',
                   'title': 'Hackers',
                   'year': '1995'}
        rv = self.app.post('/api/watchlist', data=wl_item)

        # since post redirects and not return json, test via get
        rv = self.app.get('/api/watchlist')
        self.assertTrue(10428 in [i['id'] for i in json.loads(rv.data)])

    def test_delete_from_watchlist(self):
        # add and check to it is in watchlist
        rv = self.login('dale@coop.com', '123')
        wl_item = {'id': 10428,
                   'mtype': 'movie',
                   'title': 'Hackers',
                   'year': '1995'}
        rv = self.app.post('/api/watchlist', data=wl_item)
        rv = self.app.get('/api/watchlist')
        self.assertTrue(10428 in [i['id'] for i in json.loads(rv.data)])

        # delete and check deleted
        rv = self.app.get('/watchlist/delete/movie/10428')
        rv = self.app.get('/api/watchlist')
        self.assertFalse(10428 in [i['id'] for i in json.loads(rv.data)])


if __name__ == '__main__':
    unittest.main()