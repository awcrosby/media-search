#!/usr/bin/env python
# -*- coding: utf-8 -*-
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session, json, abort)
from flask_restful import Resource, Api, reqparse
import time
import pymongo
import logging
import datetime
import requests
from wtforms import Form, StringField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps
import bottlenose as BN  # amazon product api wrapper
from bs4 import BeautifulSoup
app = Flask(__name__)
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

        # insert new user into database
        ack = insert_user_to_db({
                'name': name,
                'email': email,
                'password': password,
                'dateCreated': datetime.datetime.utcnow(),
                'watchlist': []})
        if ack:
            flash('You are now registered and can log in', 'success')
            return redirect(url_for('login'))
        else:
            flash('That email is already registered', 'danger')
    return render_template('register.html', form=form)


# user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # get form fields
        email = request.form['email']
        password_candidate = request.form['password']

        # get user by email and check password
        user = get_user_from_db(email)
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
@app.route('/watchlist', methods=['GET'])
@is_logged_in
def display_watchlist():
    mtype = request.args.get('mtype')  # retains search dropdown value

    # get user from database
    start = time.time()
    user = get_user_from_db(session['email'])

    wl_detail = []
    for item in user['watchlist']:
        full_media = get_media_from_db(item['mtype'], int(item['id']))
        if full_media:
            wl_detail.append(full_media)
        else:  # if db lookup did not return data for the item
            wl_detail.append(item)

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
    if mtype not in ['movie', 'show']:
        abort(400)

    # get summary info from themoviedb api, exit if not found
    params = {'api_key': json.loads(open('apikeys.json').read())['tmdb']}
    tmdb_url = ('https://api.themoviedb.org/3/movie/' if mtype == 'movie'
                else 'https://api.themoviedb.org/3/tv/')
    summary = requests.get(tmdb_url + str(mid), params=params)
    if summary.status_code != 200:
        flash('Media id not found', 'danger')
        return redirect(url_for('home'))
    summary = summary.json()

    # prepare to be written to db, if found as amz source
    summary['sources'] = []
    if mtype == 'movie':
        summary['year'] = summary['release_date'][:4]
        summary['mtype'] = 'movie'
    else:
        summary['title'] = summary['name']
        summary['year'] = summary['first_air_date'][:4]
        summary['mtype'] = mtype

    # check if this title/year avail on amz, if so write to db
    check_add_amz_source(media=summary)

    # get media from db to check for sources
    media = get_media_from_db(mtype, mid)

    return render_template('mediainfo.html', media=media,
                           mtype=mtype, summary=summary)


def check_add_amz_source(media):
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
    title = media['title']
    year = media['year']
    mtype = media['mtype']
    k = json.loads(open('apikeys.json').read())
    amz = BN.Amazon(k['amz_access'], k['amz_secret'],
                    k['amz_associate_tag'], MaxQPS=0.9)
    # https://github.com/lionheart/bottlenose/blob/master/README.md

    # search amz with themoviedb title
    # option to use Title instead of Keywords, but saw Spectre bad date
    if mtype == 'movie':
        results = amz.ItemSearch(
            SearchIndex='Movies',
            ResponseGroup='ItemAttributes',  # type of response
            BrowseNode='2676882011',  # product type of prime video
            Keywords='{} {}'.format(title, year))  # too many year mismatches
            # Keywords='{}'.format(title))
    else:
        results = amz.ItemSearch(
            SearchIndex='Movies',
            ResponseGroup='ItemAttributes,RelatedItems',  # type of response
            BrowseNode='2676882011',  # product type of prime video
            RelationshipType='Episode',  # necessary to get show title
            Title=title)  # Keywords option, but had 'commentary' in title

    # ensure results not empty
    soup = BeautifulSoup(results, "xml")
    if int(soup.find('TotalResults').text) == 0:
        logging.info('amz api: {}: no results found'.format(title))
        return

    # get title from first result
    if mtype == 'movie':
        if not soup.find('Item').find('ReleaseDate'):
            logging.info('amz api: {}: no rel yr in top result'.format(title))
            return  # likely means this result is obscure
        amz_title = soup.find('Item').find('Title').text  # title of 1st result
        amz_year = soup.find('Item').find('ReleaseDate').text[:4]
    else:  # note: seems difficult to get show's very first release date
        if not len(soup.find('Item').find_all('Title')) > 1:
            logging.info('amz api: {}: show title not found'.format(title))
            return
        amz_title = soup.find('Item').find_all('Title')[1].text
        pos_season = amz_title.find('Season') - 1
        amz_title = amz_title[:pos_season].rstrip('- ')

    # clean title strings and compare if a match
    t1 = title.translate({ord(c): None for c in "'’:"})
    t1 = t1.lower().replace('&', 'and')
    t2 = amz_title.translate({ord(c): None for c in "'’:"})
    t2 = t2.lower().replace('&', 'and')
    if t1 != t2:
        logging.info('amz api: {}: no title match: {} | {}'.format(title, t1, t2))
        #return

    # check movie years and compare if a match
    logging.info('amz api: {}: match found: {} | {}'.format(title, t1, t2))
    if mtype == 'movie' and amz_year != year:
        logging.warning('amz api movie year mismatch: '
            + '{}: amz: {}, tmdb: {}'.format(title, amz_year, year))

    # insert db media if not there
    insert_media_if_new(media)

    # update db media with source
    source = {'name': 'amazon',
              'display_name': 'Amazon',
              'link': soup.find('Item').find('DetailPageURL').text,
              'type': 'subscription_web_sources'}
    update_media_with_source(media, source)    


'''Section for DB calls, including REST API for browser requests'''


def get_media_from_db(mtype, mid):
    return db.Media.find_one({'mtype': mtype, 'id': mid}, {'_id': 0})


def insert_media_if_new(media):
    if not db.Media.find_one({'mtype': media['mtype'],
                              'id': media['id']}):
        db.Media.insert_one(media)
        logging.info('db wrote new media: ' + media['title'])
    return


def update_media_with_source(media, source):
    db_media = db.Media.find_one({'mtype': media['mtype'],
                                  'id': media['id']})
    if not db_media:
        logging.error('could not find media to update source')
        return
    if not any(source['name'] in d.values() for d in db_media['sources']):
        db.Media.find_one_and_update({'mtype': media['mtype'],
                                      'id': media['id']},
            {'$push': {'sources': source}})
        logging.info('{} added for: {}'.format(source['name'], media['title']))


def get_user_from_db(email):
    return db.Users.find_one({'email': email})


def insert_user_to_db(new_user):
    try:
        written_user = db.Users.insert_one(new_user)
        return written_user.acknowledged
    except pymongo.errors.DuplicateKeyError:
        return False


def get_all_watchlist_in_db():
    wl_cur = db.Users.find({}, {'_id':0, 'watchlist': 1})
    wl_all = [item for wl in wl_cur for item in wl['watchlist']]
    wl_unique = [dict(t) for t in set([tuple(d.items()) for d in wl_all])]
    return wl_unique


# route to allow browser click to initiate delete watchlist item
@app.route('/watchlist/delete/<mtype>/<int:mid>', methods=['GET'])
@is_logged_in
def delFromWatchlist(mtype=None, mid=None):
    resp = db.Users.find_one_and_update(
        {'email': session['email']},
        {'$pull': {'watchlist': {'mtype': mtype, 'id': mid}}})
    if resp:
        flash('Item deleted from watchlist', 'success')
    else:
        flash('Item not deleted from watchlist', 'danger')
    return redirect(url_for('display_watchlist'))


# REST-like API, post via browser, get only by unittest now, js in future
class WatchlistAPI(Resource):
    decorators = [is_logged_in]

    def get(self):
        user = db.Users.find_one({'email': session['email']})
        if not user:
            return '', 404
        return user['watchlist'], 200

    def post(self):
        # check if media already in watchlist and if so exit
        user = db.Users.find_one({'email': session['email']})
        wl_ids = [w['id'] for w in user['watchlist']
                  if w['mtype'] == request.form['mtype']]
        if int(request.form['id']) in wl_ids:
            # return '', 404  # return JSON if pure restful
            flash('Item already in watchlist', 'danger')
            return redirect(url_for('display_watchlist'))

        # add to user's watchlist
        d = request.form
        db.Users.find_one_and_update(
          {'email': session['email']},
          {'$push': {'watchlist':
                     {'id': int(d['id']), 'mtype': d['mtype'],
                      'title': d['title'], 'year': d['year']}}})
        # return '', 204  # return JSON if pure restful
        flash('Item added to watchlist', 'success')
        return redirect(url_for('display_watchlist'))


# set up api resource routing
api.add_resource(WatchlistAPI, '/api/watchlist')


if __name__ == "__main__":
    app.secret_key = '3d6gtrje6d2rffe2jqkv'
    app.run(host='0.0.0.0', port=8181)
