#!/usr/bin/env python
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session)
import json
import guidebox
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

'''webframework flaskapp high-level functionality:
    resolve user search query to a specific media
    search for media details in database otherwise request from guidebox api
    display streaming sources by type, with links and show ep info
    list 'did you mean' links if more than one query result was found'''

logging.basicConfig(filename='/home/awcrosby/media-search/'
                    'log/flaskapp.log',
                    format='%(asctime)s %(levelname)s: %(message)s',
                    level=logging.INFO)


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
                flash('Show already in watchlist', 'info')
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
        m = get_media(id, 'movie')
        m = add_src_display(m, 'movie')
        watchlist.append(m)
    for id in sh_ids:
        m = get_media(id, 'show')
        m = add_src_display(m, 'show')
        watchlist.append(m)

    client.close()
    print 'time to get media of full watchlist: ', time.time() - start
    print 'session.email=', email
    return render_template('watchlist.html', medias=watchlist, mtype=mtype)


# process media search
@app.route('/search', methods=['GET'])
def search(mtype='movie', query=''):
    query = request.args.get('q')  # can be string or NoneType
    mtype = request.args.get('mtype')
    session['dropdown'] = mtype

    if not query or (mtype not in ['movie', 'show', 'all']):
        return render_template('home.html')
    query = query.strip()

    guidebox.api_key = json.loads(open('apikeys.json').read())['guidebox']
    tmdb_url = 'https://api.themoviedb.org/3/search/'
    params = {
        'api_key': json.loads(open('apikeys.json').read())['tmdb'],
        'query': query
    }

    if mtype == 'all':
        # high-level search of movie and show, filtering out less popular
        mv = requests.get(tmdb_url+'movie', params=params).json()
        mv['results'] = [m for m in mv['results'] if m['vote_count'] >= 100 or 
                                                     m['popularity'] > 10]
        sh = requests.get(tmdb_url+'tv', params=params).json()
        sh['results'] = [m for m in sh['results'] if m['vote_count'] >= 100 or
                                                     m['popularity'] > 10]

        # if neither have results
        if (len(mv['results']) + len(sh['results']) == 0):
            return render_template('search.html', isresult=0,
                                   query=query, mtype='media')

        # display movie/show results on intermediate page (no sources)
        else:
            return render_template('mixedresults.html', shows=sh, movies=mv,
                                   query=query)

        # search both movie and show, first get high-level results
        mv = guidebox.Search.movies(field='title', query=query)
        sh = guidebox.Search.shows(field='title', query=query)

        # if neither return a result
        if (mv['total_results'] + sh['total_results'] == 0):
            return render_template('search.html', isresult=0,
                                   query=query, mtype='media')

        # if only one returns a result (skips the 'did you mean...' section)
        elif mv['total_results'] == 0:
            return redirect(url_for('lookup', mtype='show',
                            gbid=sh['results'][0]['id']))
        elif sh['total_results'] == 0:
            return redirect(url_for('lookup', mtype='movie',
                            gbid=mv['results'][0]['id']))

        # display movie/show results on intermediate page (no sources)
        else:
            return render_template('mixedresults.html', shows=sh, movies=mv,
                                   query=query)

    if mtype == 'movie':
        # query themoviedb
        response = requests.get(tmdb_url+'movie', params=params).json()
        print 'title from tmdb=', response['results'][0]['title']

        # get movie query results, take top result
        results = guidebox.Search.movies(field='title', query=query)
        if not (results['total_results'] > 0):  # exit early if no results
            return render_template('search.html', isresult=0,
                                   query=query, mtype=mtype)
        gbid = results['results'][0]['id']  # take first result

    elif mtype == 'show':
        # query themoviedb
        response = requests.get(tmdb_url+'tv', params=params).json()

        # get show query results, and take top result
        results = guidebox.Search.shows(field='title', query=query)
        if not (results['total_results'] > 0):  # exit early if no results
            return render_template('search.html', isresult=0,
                                   query=query, mtype=mtype)
        gbid = results['results'][0]['id']  # take first result

    # get media details from mongodb, or api search + add to mongodb
    media = get_media(gbid, mtype)

    # add display sources to the movie or show_ep dict
    media = add_src_display(media, mtype)

    # build other_results to send to template, if query was performed
    other_results = []
    for m in response['results']:
        if m['vote_count'] >= 100:
            x = {'link': '#', 'title': m['title']}
            other_results.append(x)
    '''for m in results['results'][1:5]:
        x = {'link': url_for('lookup', mtype=mtype, gbid=str(m['id'])),
             'title': m['title']}
        # if (m['wikipedia_id'] != 0) and (m['wikipedia_id'] is not None):
        other_results.append(x)  # only keep if not very obscure'''

    # logs dictionaries retrieved, either from db or api
    logging.info('user query: ' + query)
    print 'user query:', query
    logResults = open('log/search_results.log', 'w')
    pprint.pprint(results, logResults)
    logResults.close()
    logMedia = open('log/media_detail.log', 'w')
    pprint.pprint(media, logMedia)
    logMedia.close()

    return render_template('search.html', media=media, query=query,
                           mtype=mtype, other_results=other_results)


# process media id lookup
@app.route('/<mtype>/id/<int:gbid>', methods=['GET'])
def lookup(mtype='movie', gbid=None):
    mtype = 'movie' if mtype != 'show' else 'show'

    # get media details from mongodb, or api search + add to mongodb
    media = get_media(gbid, mtype)

    # add display sources to the movie or show_ep dict
    media = add_src_display(media, mtype)

    return render_template('search.html', media=media, query='',
                           mtype=mtype, other_results=[])


if __name__ == "__main__":
    app.secret_key = '3d6gtrje6d2rffe2jqkv'
    app.run(debug=True, host='0.0.0.0', port=8181)
