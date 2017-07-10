#!/usr/bin/env python
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session, abort)
from flask_restful import Resource, Api
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
from shared_func import get_media, add_src_display
from functools import wraps
app = Flask(__name__)
api = Api(app)

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

# landing page
@app.route('/')
def home():
    return render_template('home.html')


class RegisterForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=50)])
    email = StringField('Email', [validators.Length(min=6, max=50)])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')


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
                'movieq': [],
                'showq': []
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
                return redirect(url_for('watchlist'))
            else:
                return render_template('login.html', error='Invalid login')
        else:
            return render_template('login.html', error='Email not found')
    return render_template('login.html')


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


# user logout
@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('login'))


# add or delete item from watchlist is processed here, no UI
@app.route('/edit_watchlist', methods=['GET', 'POST'])
@is_logged_in
def edit_watchlist():
    if request.method == 'POST':
        # connect to db, get user, get form data
        client = pymongo.MongoClient('localhost', 27017)
        db = client.MediaData
        email = session['email']
        operation = request.form['operation']
        mtype = request.form['mtype']
        gbid = int(request.form['gbid'])

        # update the queue for movie or show
        if operation == 'add' and mtype == 'movie':
            user = db.Users.find_one({'email': email})
            if gbid not in user['movieq']:
                db.Users.find_one_and_update({'email': email},
                                             {'$push': {'movieq': gbid}})
                flash('Movie added to watchlist', 'success')
            else:
                flash('Movie already in watchlist', 'danger')
        elif operation == 'add' and mtype == 'show':
            user = db.Users.find_one({'email': email})
            if gbid not in user['showq']:
                db.Users.find_one_and_update({'email': email},
                                             {'$push': {'showq': gbid}})
                flash('Show added to watchlist', 'success')
            else:
                flash('Show already in watchlist', 'danger')
        elif operation == 'delete' and mtype == 'movie':
            db.Users.find_one_and_update({'email': email},
                                         {'$pull': {'movieq': gbid}})
            flash('Movie deleted from watchlist', 'success')
        elif operation == 'delete' and mtype == 'show':
            db.Users.find_one_and_update({'email': email},
                                         {'$pull': {'showq': gbid}})
            flash('Show deleted from watchlist', 'success')
        client.close()
    return redirect(url_for('watchlist', mtype=mtype))


# display user's watchlist
@app.route('/watchlist')
@is_logged_in
def watchlist():
    mtype = request.args.get('mtype')  # retains search dropdown value

    # connect to db and get user
    start = time.time()
    client = pymongo.MongoClient('localhost', 27017)
    db = client.MediaData
    email = session['email']
    user = db.Users.find_one({'email': email})

    # get user watchlist ids
    mv_ids = user['movieq']
    sh_ids = user['showq']

    # build watchlist to pass to template
    watchlist = []
    for id in mv_ids:
        m = get_media(id, 'movie', id)
        m = add_src_display(m, 'movie')
        watchlist.append(m)
    for id in sh_ids:
        m = get_media(id, 'show', id)
        m = add_src_display(m, 'show')
        watchlist.append(m)

    client.close()
    print 'time to get media of full watchlist: ', time.time() - start
    print 'session.email=', email
    return render_template('watchlist.html', medias=watchlist, mtype=mtype)


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
    logging.info('user query: ' + query + mtype)
    print 'user query:', query, mtype

    # perform search with themoviedb api
    mv, sh, mv['results'], sh['results'] = ({}, {}, {}, {})
    if mtype == 'movie' or mtype == 'all':
        mv = requests.get(tmdb_url+'movie', params=params).json()
        mv['results'] = [m for m in mv['results'] if m['vote_count'] >= 20 or
                                                     m['popularity'] > 10]
    if mtype == 'show' or mtype == 'all':
        sh = requests.get(tmdb_url+'tv', params=params).json()
        sh['results'] = [m for m in sh['results'] if m['vote_count'] >= 20 or
                                                     m['popularity'] > 10]

    # if neither have results render template without sending media
    if (len(mv['results']) + len(sh['results']) == 0):
        return render_template('searchresults.html', query=query)

    # if just one has results, go directly to media info page
    elif len(mv['results']) == 0:
        return redirect(url_for('mediainfo', mtype='show',
                                tmdbid=sh['results'][0]['id']))
    elif len(sh['results']) == 0:
        return redirect(url_for('mediainfo', mtype='movie',
                                tmdbid=mv['results'][0]['id']))

    # display multiple results (without sources) for user to choose
    else:
        return render_template('searchresults.html', shows=sh, movies=mv,
                               query=query)


# gets media info from database, local api
class Media(Resource):
    def get(self, media_type, media_id):
        client = pymongo.MongoClient('localhost', 27017)
        db = client.MediaData
        if media_type == 'movie':
            media = db.Movies.find_one({'themoviedb': media_id})
        else:
            media = db.Shows.find_one({'themoviedb': media_id})
        if not media:
            abort(400)
        return dumps(media)  #explicit pymongo BSON conversion to json
            
# set up api resource routing
api.add_resource(Media, '/apiv1.0/<media_type>/<int:media_id>')

# lookup via media id for mediainfo.html
@app.route('/<mtype>/id/<int:tmdbid>', methods=['GET'])
def mediainfo(mtype='movie', tmdbid=None):
    mtype = 'movie' if mtype != 'show' else 'show'

    # get summary info from themoviedb api
    if mtype == 'movie':
        tmdb_url = 'https://api.themoviedb.org/3/movie/'
    else:
        tmdb_url = 'https://api.themoviedb.org/3/tv/'
    params = {'api_key': json.loads(open('apikeys.json').read())['tmdb']}
    summary = requests.get(tmdb_url + str(tmdbid), params=params)

    # local api request
    media = requests.get(api.url_for(Media, media_type=mtype,
                                     media_id=tmdbid, _external=True))

    # add display sources
    if media:
        media = json.loads(media.json())
        media = add_src_display(media, mtype)

    if summary.status_code != 200:
        flash('Media id not found', 'danger')
        return redirect(url_for('home'))

    return render_template('mediainfo.html', media=media,
                           mtype=mtype, summary=summary.json())


if __name__ == "__main__":
    app.secret_key = '3d6gtrje6d2rffe2jqkv'
    app.run(debug=True, host='0.0.0.0', port=8181)
