#!/usr/bin/env python
from flask import Flask, render_template, request, redirect, url_for, flash, session, logging
import json
import guidebox
import time
import urllib
import pymongo
import pprint
import logging
import datetime
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from shared_func import get_media, get_show_ep, get_all_ep, add_src_display
app = Flask(__name__)
from functools import wraps

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
    return render_template('index.html')


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
            db.Users.insert_one(
            {
                'name': name,
                'email': email,
                'password': password,
                'dateCreated': datetime.datetime.utcnow(),
                'movieq': [],
                'showq': []
            })
        except pymongo.errors.DuplicateKeyError, e:
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
        user = db.Users.find_one( {'email': email} )
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
                flash('Movie already in watchlist', 'info')
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
    return redirect(url_for('watchlist'))


# display user's watchlist
@app.route('/watchlist')
@is_logged_in
def watchlist():
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
    return render_template('watchlist.html', medias=watchlist)


# process media search or id lookup and display
@app.route('/<mtype>/id/<int:gbid>')
@app.route('/search', methods=['GET'])
def search(mtype='movie', gbid=None, query=''):
    # get query, then resolve mtype from url path or GET args
    query = request.args.get('q')  # can be string or NoneType
    if query:
        mtype = 'movie' if request.args.get('mtype') != 'show' else 'show'
        query = query.strip()
    elif gbid:
        mtype = 'movie' if mtype != 'show' else 'show'
        query = ''
        
    if not (query or gbid):
        return render_template('index.html')

    guidebox.api_key = json.loads(open('apikeys.json').read())['guidebox']

    if mtype == 'movie':
        # get movie query results, take top result, unless id passed in
        if query:
            results = guidebox.Search.movies(field='title', query=query)
            if not (results['total_results'] > 0):  # exit early if no results
                return render_template('index.html', isresult=0,
                                       query=query, mtype=mtype)
            gbid = results['results'][0]['id']  # take first result

    elif mtype == 'show':
        # get show query results, and take top result, unless id passed in
        if query:
            results = guidebox.Search.shows(field='title', query=query)
            if not (results['total_results'] > 0):  # exit early if no results
                return render_template('index.html', isresult=0,
                                       query=query, mtype=mtype)
            gbid = results['results'][0]['id']  # take first result

    # get media details from mongodb, or api search + add to mongodb
    media = get_media(gbid, mtype)

    # add display sources to the movie or show_ep dict
    media = add_src_display(media, mtype)

    # build other_results to send to template, if query was performed
    other_results = []
    if query:
        for m in results['results'][1:5]:
            # t = urllib.quote(m['title'].encode('utf-8'))  # percent encoded
            x = {'link': url_for('search', mtype=mtype, gbid=str(m['id'])), 'title': m['title']}
            # if (m['wikipedia_id'] != 0) and (m['wikipedia_id'] is not None):
            other_results.append(x)  # only keep if not very obscure

    # logs dictionaries retrieved, either from db or api
    if query:
        logging.info('user query: ' + query)
        print 'user query:', query
        logResults = open('log/search_results.log', 'w')
        pprint.pprint(results, logResults)
        logResults.close()
        logMedia = open('log/media_detail.log', 'w')
        pprint.pprint(media, logMedia)
        logMedia.close()

    return render_template('index.html', media=media, query=query,
                           mtype=mtype, other_results=other_results)


if __name__ == "__main__":
    app.secret_key='3d6gtrje6d2rffe2jqkv'
    app.run(debug=True, host='0.0.0.0', port=8181)
