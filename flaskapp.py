#!/usr/bin/env python
# -*- coding: utf-8 -*-
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session, abort, jsonify)
from flask_restful import Resource, Api, reqparse
from bson.json_util import dumps
import json
import time
import pymongo
import pprint
import logging
import datetime
import requests
from wtforms import Form, StringField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps
import bottlenose as BN  # amazon product api wrapper
from bs4 import BeautifulSoup
import provider_search
app = Flask(__name__)
#app.config['TESTING'] = True
api = Api(app)
db = pymongo.MongoClient('localhost', 27017).MediaData

'''webframework flaskapp high-level functionality:
    user search query via themoviedb api, results with links to specific media
    lookup movie info from database
    display streaming sources by type, with links and show ep info
    support user login to create and edit a watchlist'''

logging.basicConfig(filename='/home/awcrosby/media-search/'
                    'log/flaskapp.log',
                    format='%(asctime)s %(levelname)s: %(message)s',
                    level=logging.INFO)
app.secret_key = '3d6gtrje6d2rffe2jqkv'
parser = reqparse.RequestParser()


# check if users logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, please login', 'danger')
            return redirect(url_for('login'))
    return wrap


class RegisterForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=50)])
    email = StringField('Email', [validators.Length(min=6, max=50)])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')


# landing page
@app.route('/')
def home():
    return render_template('home.html')


# about page
@app.route('/about')
@is_logged_in
def about():
    return render_template('about.html')


# user registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        # get form fields
        name = form.name.data
        email = form.email.data
        password = sha256_crypt.encrypt(str(form.password.data))

        # connect to db and insert new user
        client = pymongo.MongoClient('localhost', 27017)
        db = client.MediaData
        try:
            db.Users.insert_one({
                'name': name,
                'email': email,
                'password': password,
                'dateCreated': datetime.datetime.utcnow(),
                'watchlist': []
            })
        except pymongo.errors.DuplicateKeyError:
            flash('That email is already registered', 'danger')
            return redirect(url_for('register'))

        flash('You are now registered and can log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


# user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # get form fields
        email = request.form['email']
        password_candidate = request.form['password']

        # connect to db
        client = pymongo.MongoClient('localhost', 27017)
        db = client.MediaData

        # get user by email and check password
        user = db.Users.find_one({'email': email})
        if user:
            if sha256_crypt.verify(password_candidate, user['password']):
                # passwords match
                session['logged_in'] = True
                session['email'] = email
                flash('You are now logged in', 'success')
                return redirect(url_for('display_watchlist'))
            else:
                return render_template('login.html', error='Invalid login')
        else:
            return render_template('login.html', error='Email not found')
    return render_template('login.html')


# user logout
@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('login'))


# GET display user's watchlist, or POST new item to watchlist
@app.route('/watchlist', methods=['GET', 'POST'])
@is_logged_in
def display_watchlist():
    if request.method == 'POST':
        response = requests.post(api.url_for(Wlist, _external=True),
            data={
                'mid': request.form['mid'], 'mtype': request.form['mtype'],
                'title': request.form['title'], 'year': request.form['year'],
                'email': session['email']})
        if response.status_code == 204:
            flash('Item added to watchlist', 'success')
        elif response.status_code == 404:
            flash('Item already in watchlist', 'danger')
        else:
            flash('Item not added to watchlist', 'danger')
        return redirect(url_for('display_watchlist'))
        
    mtype = request.args.get('mtype')  # retains search dropdown value

    # connect to db and get user     TODO use api here
    start = time.time()
    db = pymongo.MongoClient('localhost', 27017).MediaData
    user = db.Users.find_one({'email': session['email']})

    wl_detail = []
    for item in user['watchlist']:
        m = requests.get(api.url_for(Media, mtype=item['mtype'],
                                     mid=int(item['id']), _external=True))
        if m.status_code == 200:
            m = json.loads(m.json())
            wl_detail.append(m)
        else:  # if api did not return data for the item
            wl_detail.append(item)

        #wl_detail.append(item)

    print 'time to get media of full watchlist: ', time.time() - start
    return render_template('watchlist.html', medias=wl_detail, mtype=mtype)


# send user query to themoviedb api and return json
@app.route('/search', methods=['GET'])
def search(mtype='movie', query=''):
    # ensure GET data is valid
    query = request.args.get('q')  # can be string or NoneType
    mtype = request.args.get('mtype')
    session['dropdown'] = mtype
    if not query or (mtype not in ['movie', 'show', 'all']):
        return render_template('home.html')
    query = query.strip()

    # setup api interaction and log query
    tmdb_url = 'https://api.themoviedb.org/3/search/'
    params = {
        'api_key': json.loads(open('apikeys.json').read())['tmdb'],
        'query': query
    }
    logging.info('user query, {}: {}'.format(mtype, query))
    print 'user query, {}: {}'.format(mtype, query)

    # search via themoviedb api, take first result and any pop others
    mv, sh, mv['results'], sh['results'] = ({}, {}, [], [])
    if mtype == 'movie' or mtype == 'all':
        mv = requests.get(tmdb_url+'movie', params=params).json()
        pop_after_first = [m for m in mv['results'][1:]
                           if m['vote_count'] >= 10 or m['popularity'] > 10]
        mv['results'] = [m for m in mv['results'][:1]] + pop_after_first
        mv['results'] = [m for m in mv['results'] if m['release_date']]
        mv['results'] = [m for m in mv['results'] if m['poster_path']]
    if mtype == 'show' or mtype == 'all':
        sh = requests.get(tmdb_url+'tv', params=params).json()
        pop_after_first = [m for m in sh['results'][1:]
                           if m['vote_count'] >= 10 or m['popularity'] > 10]
        sh['results'] = [m for m in sh['results'][:1]] + pop_after_first
        sh['results'] = [m for m in sh['results'] if m['first_air_date']]
        sh['results'] = [m for m in sh['results'] if m['poster_path']]

    # if neither have results render template without sending media
    if (len(mv['results']) + len(sh['results']) == 0):
        return render_template('searchresults.html', query=query)

    # if just one has results, go directly to media info page
    elif len(sh['results']) == 0 and len(mv['results']) == 1:
        return redirect(url_for('mediainfo', mtype='movie',
                                mid=mv['results'][0]['id']))
    elif len(mv['results']) == 0 and len(sh['results']) == 1:
        return redirect(url_for('mediainfo', mtype='show',
                                mid=sh['results'][0]['id']))

    # display multiple results (without sources) for user to choose
    else:
        return render_template('searchresults.html', shows=sh, movies=mv,
                               query=query)


# lookup via media id for mediainfo.html
@app.route('/<mtype>/id/<int:mid>', methods=['GET'])
def mediainfo(mtype='movie', mid=None):
    mtype = 'movie' if mtype != 'show' else 'show'

    # get summary info from themoviedb api, exit if not found
    params = {'api_key': json.loads(open('apikeys.json').read())['tmdb']}
    tmdb_url = ('https://api.themoviedb.org/3/movie/' if mtype == 'movie'
        else 'https://api.themoviedb.org/3/tv/')
    summary = requests.get(tmdb_url + str(mid), params=params)
    if summary.status_code != 200:
        flash('Media id not found', 'danger')
        return redirect(url_for('home'))
    summary = summary.json()
    if mtype == 'movie':
        summary['year'] = summary['release_date'][:4]
    else:
        summary['title'] = summary['name']
        summary['year'] = summary['first_air_date'][:4]

    # check if this title/year avail on amz and write to db
    check_add_amz_source(summary['title'], summary['year'], mtype)

    # local api request to check for sources
    media = requests.get(api.url_for(Media, mtype=mtype,
                                     mid=mid, _external=True))
    if media.status_code == 200:
        media = json.loads(media.json())

    return render_template('mediainfo.html', media=media,
                           mtype=mtype, summary=summary)


def check_add_amz_source(title, year, mtype):
    '''Non-Amz approach: scrape title then search themoviedb for 1st result
       ok because its searching in ~all media ever
       Amz: themoviedb title to search amz 1st result not ok: any Terminator
       movie title yields Genisys, so check if title/year exact match'''

    '''search amz for "Where The Red Fern Grows" it has 2003 as top result,
            themoviedb is 1974, mismatch
       search amz for "Where The Red Fern Grows 1974" it matches
       search amz for "Clear and Present Danger 1994" yields no results
       search amz for "Clear and Present Danger" it matches
            also "Chaos", "The Assignment"... amz has many date issues either
            mismatch or uses date of a re-release in ItemSearch results'''

    # prepare for amz api search
    k = json.loads(open('apikeys.json').read())
    amz = BN.Amazon(k['amz_access'], k['amz_secret'],k['amz_associate_tag'],
          MaxQPS=2)
    # https://github.com/lionheart/bottlenose/blob/master/README.md

    # search amz with themoviedb title
    # option to use Title instead of Keywords, but saw Spectre bad date
    if mtype == 'movie':
        results = amz.ItemSearch(SearchIndex='Movies',
            ResponseGroup='ItemAttributes',  # type of response
            BrowseNode='2676882011',  # product type of prime video
            #Keywords='{} {}'.format(title, year))  # too many year mismatches
            Keywords='{}'.format(title))
    else:
        results = amz.ItemSearch(SearchIndex='Movies',
            ResponseGroup='ItemAttributes,RelatedItems',  # type of response
            BrowseNode='2676882011',  # product type of prime video
            RelationshipType='Episode',  # necessary to get show title
            Title=title)  #  Keywords option, but had 'commentary' in title

    # ensure results not empty and release data is present
    soup = BeautifulSoup(results, "xml")
    if int(soup.find('TotalResults').text) == 0:
        logging.info('amazon api - no results found')
        return

    # get title from first result
    if mtype == 'movie':
        if not soup.find('Item').find('ReleaseDate'):
            logging.info('amazon api - no release year in top result')
            return  # likely means this result is obscure
        amz_title = soup.find('Item').find('Title').text  # title of 1st result
        amz_year = soup.find('Item').find('ReleaseDate').text[:4]
        print 'themoviedb: {}, amazon: {}'.format(year, amz_year)
    else:  # note: seems difficult to get show's very first release date
        if not len(soup.find('Item').find_all('Title')) > 1:
            logging.info('amazon api - show title not found')
            return
        amz_title = soup.find('Item').find_all('Title')[1].text
        pos_season = amz_title.find('Season') - 1
        amz_title = amz_title[:pos_season]
        amz_title = amz_title.rstrip('- ')

    # clean title strings and compare, if title and year match, it is a match
    t1 = title.translate({ord(c): None for c in "'’:"})
    t1 = t1.lower().replace('&', 'and')
    t2 = amz_title.translate({ord(c): None for c in "'’:"})
    t2 = t2.lower().replace('&', 'and')
    if t1 != t2:
        logging.info('amazon api, no match: {}, {}'.format(t1, t2))
        return

    # append amazon source
    logging.info('amazon api - found title match')
    source = {'name': 'amazon',
              'display_name': 'Amazon',
              'link': 'http://www.amazon.com',
              'type': 'subscription_web_sources'}
    media = {'title': title, 'link': soup.find('Item').find('DetailPageURL').text}
    provider_search.lookup_and_write_medias([media], mtype, source)


# route to allow browser click to make HTTP DELETE request
@app.route('/watchlist/delete/<mtype>/<int:mid>', methods=['GET'])
@is_logged_in
def delFromWatchlist(mtype=None, mid=None):
    response = requests.delete(api.url_for(WlistItem, mtype=mtype,
                 mid=mid, _external=True, email=session['email']))
    if response.status_code == 204:
        flash('Item deleted from watchlist', 'success')
    else:
        flash('Item not deleted from watchlist', 'danger')
    return redirect(url_for('display_watchlist'))


'''Local API Section'''
class Media(Resource):
    def get(self, mtype, mid):
        media = db.Media.find_one({'mtype': mtype, 'id': mid})
        if not media:
            return '', 404
        return dumps(media), 200  # pymongo BSON conversion to json
    # TODO create a POST here
    # TODO create a PUT here to update source new or update active=False


class User(Resource):
    decorators = [is_logged_in]
    def get(self):
        user = db.Users.find_one({'email': session['email']})
        if not user:
            return '', 404
        return dumps(user), 200


# local api, watchlist, GET all or POST one
class Wlist(Resource):
    def get(self):
        db = pymongo.MongoClient('localhost', 27017).MediaData
        email = session['email']
        user = db.Users.find_one({'email': email})
        return user['watchlist']
    def post(self):
        db = pymongo.MongoClient('localhost', 27017).MediaData

        # check if media already in watchlist and if so exit
        user = db.Users.find_one({'email': request.form['email']})
        all_mids = [w['id'] for w in user['watchlist']
                   if w['mtype'] == request.form['mtype']]
        if int(request.form['mid']) in all_mids:
            return '', 404

        # add to user's watchlist
        db.Users.find_one_and_update({'email': request.form['email']},
          {'$push': {'watchlist':
            {'id': int(request.form['mid']), 'mtype': request.form['mtype'],
             'title': request.form['title'], 'year': request.form['year']}}})
        return '', 204


# local api, watchlist, DELETE one
class WlistItem(Resource):
    def delete(self, mtype, mid, email):
        db = pymongo.MongoClient('localhost', 27017).MediaData
        db.Users.find_one_and_update({'email': email},
            {'$pull': {'watchlist': {'mtype': mtype, 'id': mid}}})
        return '', 204

# set up api resource routing, TODO add auth on POST and DELETE requests
api.add_resource(Media, '/api/<mtype>/<int:mid>')
api.add_resource(User, '/api/user')
api.add_resource(Wlist, '/api/watchlist')
api.add_resource(WlistItem, '/api/watchlist/<mtype>/<int:mid>/<email>')


if __name__ == "__main__":
    app.secret_key = '3d6gtrje6d2rffe2jqkv'
    app.run(host='0.0.0.0', port=8181)
