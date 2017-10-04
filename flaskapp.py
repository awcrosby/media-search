#!/usr/bin/env python
# -*- coding: utf-8 -*-
# flaskapp.py

from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session, json, abort)
from flask_restful import Resource, Api, reqparse
import time
import pymongo
import logging
from datetime import datetime, timedelta
import requests
import re
from wtforms import Form, StringField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps
import bottlenose as BN  # amazon product api wrapper
from bs4 import BeautifulSoup
import urllib
app = Flask(__name__)
api = Api(app)
db = pymongo.MongoClient('localhost', 27017).MediaData

'''webframework flaskapp high-level functionality:
    user search query via themoviedb api, results with links to specific media
    lookup movie info from database
    display streaming sources by type, with links and show ep info
    support user login to create and edit a watchlist'''

logging.basicConfig(filename='log/flaskapp.log',
                    format='%(asctime)s %(levelname)s: %(message)s',
                    level=logging.INFO)
app.secret_key = '3d6gtrje6d2rffe2jqkv'
parser = reqparse.RequestParser()


# initialize database by creating collection and unique index
def init_database():
    db.Media.create_index([('mtype', pymongo.ASCENDING),
                           ('id', pymongo.ASCENDING)], unique=True)
    db.Users.create_index('email', unique=True)


def reindex_database():
    db.Media.reindex()


#@app.after_request  # attempt to add headers, but didnt update page on change
#def add_header(response):
#    response.cache_control.max_age = 360
#    return response


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
                'dateCreated': datetime.utcnow(),
                'watchlist': []})
        if ack:
            flash('You are now registered and can log in', 'success')
            return redirect(url_for('login'))
        else:
            flash('Error - email may already be registered', 'danger')
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


# display user's watchlist
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
            m = {k:v for (k,v) in full_media.items() if k in
                 ['title', 'sources', 'mtype', 'year', 'id']}
            wl_detail.append(m)
        else:  # if db lookup did not return data for the item
            item['sources'] = []
            wl_detail.append(item)

    watchlist = json.dumps(wl_detail)
    logging.info(u'time to get media of full watchlist: {:.3f}s'.format(time.time()-start))
    return render_template('watchlist.html', medias=wl_detail, watchlist=watchlist, mtype=mtype)


# send user query to themoviedb api and return results or single mediainfo.html
@app.route('/search', methods=['GET'])
def search(mtype='movie', query=''):
    # ensure GET data is valid, and prepare for search
    query = request.args.get('q')  # can be string or NoneType
    mtype = request.args.get('mtype')
    if not query or (mtype not in ['movie', 'show', 'all']):
        return render_template('home.html')
    session['dropdown'] = mtype
    query = query.strip()
    logging.info(u'user query, {}: {}'.format(mtype, query))

    # search via themoviedb api, take first result and any pop others
    mv, sh, mv['results'], sh['results'] = ({}, {}, [], [])
    if mtype == 'movie' or mtype == 'all':
        mv = themoviedb_search(query, 'movie')
        pop_after_first = [m for m in mv['results'][1:]
                           if m['vote_count'] >= 10 or m['popularity'] > 10]
        mv['results'] = [m for m in mv['results'][:1]] + pop_after_first
        mv['results'] = [m for m in mv['results'] if m['release_date']]
        mv['results'] = [m for m in mv['results'] if m['poster_path']]
    if mtype == 'show' or mtype == 'all':
        sh = themoviedb_search(query, 'show')
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
                                mid=mv['results'][0]['id'], q=query))
    elif len(mv['results']) == 0 and len(sh['results']) == 1:
        return redirect(url_for('mediainfo', mtype='show',
                                mid=sh['results'][0]['id'], q=query))

    # display multiple results (without sources) for user to choose
    else:
        return render_template('searchresults.html', shows=sh, movies=mv,
                               query=query)


# search themoviedb via user query or scraped title
def themoviedb_search(query, mtype):
    tmdb_url = 'https://api.themoviedb.org/3/search/'
    with open('creds.json', 'r') as f:
        params = {'api_key': json.loads(f.read())['tmdb']}

    # if year is in query, remove and use as search param
    if re.search('\([0-9][0-9][0-9][0-9]\)$', query):
        title_year = query[-5:-1]
        query = query[:-6].strip()
        params['year'] = title_year

    # lookup media dict from themoviedb
    params['query'] = query
    search_type = 'movie' if mtype == 'movie' else 'tv'
    return requests.get(tmdb_url+search_type, params=params).json()


# lookup via media id for mediainfo.html
@app.route('/<mtype>/id/<int:mid>', methods=['GET'])
def mediainfo(mtype='', mid=None):
    query = request.args.get('q')  # can be string or NoneType
    if not query:
        query = ''

    if mtype not in ['movie', 'show']:
        abort(400)

    # get summary info from themoviedb api, exit if not found
    api_media = themoviedb_lookup(mtype, mid)
    if not api_media:
        flash('Media id not found', 'danger')
        return redirect(url_for('home'))

    # check if this title/year avail on amz, if so write to db
    check_add_amz_source(api_media, source_name='amazon')
    check_add_amz_source(api_media, source_name='amazon_pay')

    # get media from db to check for sources
    db_media = get_media_from_db(mtype, mid)

    # set media to be combo of api and whatever in db
    media = api_media.copy()
    if db_media:
        media.update(db_media)

    # get json version of sources for javascript to use 
    sources = json.dumps(media['sources'])

    return render_template('mediainfo.html', media=media,
                           mtype=mtype, sources=sources, query=query)


# lookup themoviedb media via id
def themoviedb_lookup(mtype, id):
    with open('creds.json', 'r') as f:
        params = {'api_key': json.loads(f.read())['tmdb'],
                  'append_to_response': 'credits'}
    tmdb_url = ('https://api.themoviedb.org/3/movie/' if mtype == 'movie'
                else 'https://api.themoviedb.org/3/tv/')
    media = requests.get(tmdb_url + str(id), params=params)
    if media.status_code != 200:
        return

    # in case this is written to db, add needed keys
    media = media.json()
    media['sources'] = []
    if mtype == 'movie':
        media['year'] = media['release_date'][:4]
        media['mtype'] = 'movie'
    else:
        media['title'] = media['name']
        media['year'] = media['first_air_date'][:4]
        media['mtype'] = mtype
    return media


def check_add_amz_source(media, source_name):
    # check if amz source exists and is recent, if so then exit
    dt = datetime.utcnow() - timedelta(days=0)  #TODO TEMP changed from 7 to 0
    x = db.Media.find_one({'mtype': media['mtype'],
                           'id': media['id'],
                           'sources':
                             {'$elemMatch':
                               {'name': source_name,
                                'last_updated': {'$gt': dt} }}})
    if x:
        logging.info(u'AMZ source already in db, {}: {}'.format(source_name,
                                                        media['title']))
        return

    # prepare for amz api search
    title = media['title']
    year = media['year']
    mtype = media['mtype']
    director = ''
    if mtype == 'movie' and 'credits' in media:
        crew = media['credits']['crew']
        director = [c['name'] for c in crew if c['job'] == 'Director']
        director = director[0] if director else ''
        director = director.replace('Dave', 'David')
        if title == 'Terminator Genisys':  # put misspelling so will match
            director = director.replace('Taylor', 'Talyor')
    #   logging.info(u'amz mv params: {}, direct: {}'.format(title, director))
    with open('creds.json', 'r') as f:
        k = json.loads(f.read())
    amz = BN.Amazon(k['amz_access'], k['amz_secret'],
                    k['amz_associate_tag'], MaxQPS=0.9)
    # https://github.com/lionheart/bottlenose/blob/master/README.md

    # set parameters to use function as prime or pay
    if source_name == 'amazon':
        browse_node = '2676882011'
    elif source_name == 'amazon_pay':
        browse_node = '2625373011'  # Movies & TV, the highest ancestor
        # TEMP? changed from 2858778011, Amz Video

    # search amz with themoviedb info
    try:
        logging.info('MAKE AMZ REQUEST')
        if mtype == 'movie':
            results = amz.ItemSearch(
                SearchIndex='Movies',
                ResponseGroup='ItemAttributes,OfferSummary',  # type of response
                BrowseNode=browse_node,  # product type of prime video
                Title=title,
                Keywords=director)
        else:
            results = amz.ItemSearch(
                SearchIndex='Movies',
                ResponseGroup='ItemAttributes,RelatedItems,OfferSummary',
                BrowseNode=browse_node,  # product type of prime video
                RelationshipType='Episode',  # necessary to get show title
                Title=title)
    except urllib.error.HTTPError as e:
        logging.error(u'AMZ API HTTP ERROR, {}: {}'.format(source_name, title))
        logging.exception(e)
        return

    # ensure results not empty
    soup = BeautifulSoup(results, "xml")
    if int(soup.find('TotalResults').text) == 0:
        logging.info(u'AMZ API no match, {}: {}'.format(source_name, title))
        return

    # exit if missing data and log match
    if mtype == 'movie':
        if not soup.find('Item').find('ReleaseDate'):
            logging.warning(u'AMZ API no rel yr, {}: {}'.format(source_name, title))
            return  # likely means this result is obscure
        amz_title = soup.find('Item').find('Title').text  # title of 1st result
        amz_year = soup.find('Item').find('ReleaseDate').text[:4]
    else:
        if ((not soup.find('Item')) or
            (not soup.find('Item').find('Title'))):
            logging.warning(u'AMZ API no title, {}: {}'.format(source_name, title))
            return
        amz_title = soup.find('Item').find_all('Title')[-1].text

        amz_year = ''  # not used to compare, can't easily get 1st release date
        # can get series with another api call:
        # https://stackoverflow.com/questions/8014934/

        if not doTitlesMatch(title, amz_title):
            # title mismatch on show worse than movie since no director search
            logging.warning(u'AMZ API show title mismatch, {}: '
                            'tmdb:{}, amz:{}'.format(source_name, title, amz_title))
            return

    logging.info(u'AMZ API match, {}: {}: amz{}, tmdb{}'.format(
        source_name, title, amz_year, year))

    # insert db media if not there
    insert_media_if_new(media)

    # update db media with source
    source = {'name': source_name,
              'display_name': source_name,
              'link': soup.find('Item').find('DetailPageURL').text}

    if source_name == 'amazon_pay':
        products = []
        for item in soup.find_all('Item'):
            attr = item.find('ItemAttributes')
            ptype = attr.find('ProductTypeName').text

            # skip product if ProductType is not expected
            if (not (ptype == 'DOWNLOADABLE_TV_SEASON' and mtype == 'show') and
                not (ptype == 'DOWNLOADABLE_MOVIE' and mtype == 'movie') and
                not  ptype == 'ABIS_DVD'):
                continue

            logging.info(u'productTypeName: {}'.format(ptype))

            # skip product if no price or title mis-match
            if not attr.find('ListPrice'):
                #logging.info('product has no price')
                continue
            if ((mtype == 'show' or mtype == 'movie') and
                not doTitlesMatch(title, attr.find('Title').text)):
                #logging.info(u'title mismatch: {} | {}'.format(title,
                #             attr.find('Title').text))
                continue

            # skip if movie amz title has year and very diff than themoviedb
            try:
                amz_title = attr.find('Title').text
                if (mtype == 'movie' and
                    re.search('\([0-9][0-9][0-9][0-9]\)$', amz_title)):
                    amz_year = int(amz_title[-5:-1])  # assume year at end
                    tmdb_year = int(year)
                    if abs(amz_year - tmdb_year) > 1:
                        logging.info('year in title, diff > 1')
                        continue
            except Exception as e:
                logging.exception('error finding or converting year to int')
                continue

            # create product object
            logging.info('adding product')
            prod = {}

            if ptype == 'DOWNLOADABLE_TV_SEASON':  # no offer on relateditems
                prod['price'] = attr.find('ListPrice').find(
                                'FormattedPrice').text
            else: 
                prod['price'] = item.find('OfferSummary').find(
                                'LowestNewPrice').find('FormattedPrice').text
            prod['price'] = prod['price'].replace('Too low to display', '')

            prod['title'] = attr.find('Title').text
            prod['link'] = item.find('DetailPageURL').text
            if ptype == 'ABIS_DVD':
                prod['type'] = 'disc'
            else:
                prod['type'] = 'stream'

            # shorten DVD title
            if ptype == 'ABIS_DVD' and mtype == 'show':
                prod['title'] = prod['title'].replace('The Complete', '')
                prod['title'] = prod['title'].replace(' ,', '')

            # add product to product list
            products.append(prod)
            continue

            # try to get a better price description, but often captcha
            if ptype == 'DOWNLOADABLE_MOVIE':
                r = requests.get(prod['link'].split('?')[0])
                html = BeautifulSoup(r.text, 'html.parser')
                if not html.find_all('input', {'data-quality': 'SD'}):
                    logging.warning('recaptcha')
                for i in html.find_all('input', {'data-quality': 'SD'}):
                    if i.get('value').startswith('Rent Movie SD $'):
                        prod['price'] = i.get('value')
                        break
                    elif i.get('value').startswith('Buy Movie SD $'):
                        prod['price'] = i.get('value')
            elif ptype == 'DOWNLOADABLE_TV_SEASON':
                r = requests.get(prod['link'].split('?')[0])
                html = BeautifulSoup(r.text, 'html.parser')
                if not html.find_all('input', {'data-quality': 'SD'}):
                    logging.warning('recaptcha')
                for i in html.find_all('input', {'data-quality': 'SD'}):
                    logging.info('i= {}'.format(i))
                    if i.get('value').startswith('Buy Season'):
                        prod['price'] = i.get('value')
                        prod['title'] = prod['title'].split('Season')[0]
                        prod['title'] = prod['title'].strip(' ,')

            # add product to product list
            products.append(prod)

        products = sorted(products, key=lambda k: k['title'])
        products = sorted(products, key=lambda k: k['type'], reverse=True)
        source['products'] = products

    update_media_with_source(media, source)


def doTitlesMatch(t1, t2):
    def distill(t):
        # special section for bad matches
        if 'Cast & Creators' in t: return None  # prevent fam guy fal pos
        t = t.replace('Terminator 4: Salvation', 'Terminator Salvation')
        t = t.replace('Terminator: Genisys', 'Terminator Genisys')

        t = t.lower().replace('&', 'and').replace('the ', '')
        t = t.replace('original classic ', '')
        for x in ['season', 'ssn', 'series', 'volume', 'blu-ray', '(', ':']:
            t = t.split(x)[0]  # take left of word, for amz seasons
        t = t.translate({ord(c): None for c in ":'’-,[]()"}).strip()  # remove
        t = t.replace(' ii', ' 2').replace(' iii', ' 3').replace(' iv', ' 4')
        return t
        # note: when ignore right of ':' bad for 'Tron' != 'Tron: Legacy'
        #       but good for 'Blade Runner: The Final Cut'
    return distill(t1) == distill(t2)


'''Section for DB calls, including REST API for browser requests'''


def get_media_from_db(mtype, mid):
    return db.Media.find_one({'mtype': mtype, 'id': mid}, {'_id': 0})


def db_lookup_via_link(link):
    return db.Media.find_one({'sources.link': link}, {'_id': 0})


def insert_media_if_new(media):
    if not db.Media.find_one({'mtype': media['mtype'],
                              'id': media['id']}):
        db.Media.insert_one(media)
        logging.info(u'db wrote new media: {}'.format(media['title']))
    return


def update_media_with_source(media, source):
    # get media from database and exit if errors
    m = db.Media.find_one({'mtype': media['mtype'],
                                  'id': media['id']})
    if not m:
        logging.error(u'could not find media to update source')
        return
    if 'sources' not in m:
        logging.error(u'unexpected, db media exists with no sources list')
        return

    if not any(source['name'] in d.values() for d in m['sources']):
        logging.info(u'adding {} source for: {}'.format(source['name'],
                                                       media['title']))

    # delete source if it exists
    db.Media.find_one_and_update({'mtype': m['mtype'], 'id': m['id']},
                                 {'$pull': {'sources':
                                             {'name': source['name']}}})

    # add source with last_updated timestamp
    source['last_updated'] = datetime.utcnow()
    db.Media.find_one_and_update({'mtype': m['mtype'], 'id': m['id']},
                                 {'$push': {'sources': source}})


def remove_old_sources(source_name):
    ''' when media found on provider site, it's updated with timestamp,
        any source with old timestamp is no longer avail...
        set timedelta to no less than any provider takes to search '''
    dt = datetime.utcnow() - timedelta(minutes=120)
    x = db.Media.update_many(
        {'sources': {'$elemMatch':
                        {'name': source_name,
                         'last_updated': {'$lt': dt} }}},
        {'$pull': {'sources': {'name': source_name}}})

    logging.info(u'removed {} source from {} media'.format(source_name,
                                                           x.matched_count))
    return


def get_user_from_db(email):
    return db.Users.find_one({'email': email})


def insert_user_to_db(new_user):
    try:
        written_user = db.Users.insert_one(new_user)
        return written_user.acknowledged
    except pymongo.errors.DuplicateKeyError:
        return False


def get_all_watchlist_in_db():
    wl_cur = db.Users.find({}, {'_id': 0, 'watchlist': 1})
    wl_all = [item for wl in wl_cur for item in wl['watchlist']]
    wl_unique = [dict(t) for t in set([tuple(d.items()) for d in wl_all])]
    return wl_unique


def remove_hulu_addon_media():
    '''on browse of hulu, for media requiring addons (i.e. showtime) it does
    not denote this in html (only in an img), so any overlaps with both
    sources will remove hulu as a source, called from provider_search.py'''
    x = db.Media.update_many({'sources.name': {'$all': ['hulu', 'showtime']}},
                             {'$pull': {'sources': {'name': 'hulu'}}})
    logging.info('hulu removed from {0!s} db docs'.format(x.matched_count))
    return


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


# REST-like API, HTTP DELETE to delete item, for js in future
class WlistDelAPI(Resource):
    def delete(self, mtype, mid, email):
        flash('DELETE API function called', 'success')
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
api.add_resource(WlistDelAPI, '/api/watchlist_del')
api.add_resource(WatchlistAPI, '/api/watchlist')


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8181)
