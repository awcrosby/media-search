#!/usr/bin/env python
from flask import Flask, render_template, request
import json
import guidebox
import time
import urllib
import pymongo
import pprint
import logging
from shared_func import get_all_ep, add_src_display
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


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/list')
def showlist():
    client = pymongo.MongoClient('localhost', 27017)
    db = client.MediaData
    movies = list(db.Movies.find().limit(7))  # results in mem, not db cursor
    shows = list(db.Shows.find().limit(7))  # results in mem, not db cursor
 
    for m in movies:
        m = add_src_display(m, 'movie')
    for m in shows:
        m = add_src_display(m, 'show')
    medias = movies + shows   
    
    return render_template('list.html', medias=medias)


@app.route('/search', methods=['GET'])
def search():
    # get form data (unicode), and exit early if query is blank
    query = request.args.get('q')
    qtype = request.args.get('mtype')
    if not query:
        return render_template('index.html')

    # prepare for search and connect to database
    guidebox.api_key = json.loads(open('apikeys.json').read())['guidebox']
    logging.info('user query: ' + query)
    print 'user query: ', query
    start = time.time()
    client = pymongo.MongoClient('localhost', 27017)
    db = client.MediaData

    if qtype == 'movie':
        # get movie query results, and take top result
        results = guidebox.Search.movies(field='title', query=query)
        if not (results['total_results'] > 0):  # exit early if no results
            return render_template('index.html', isresult=0,
                                   query=query, qtype=qtype)
        gbid = results['results'][0]['id']  # take first result

        # get movie details from mongodb, or api search and add to mongodb
        media = db.Movies.find_one({'id': gbid})
        if not media:
            media = guidebox.Movie.retrieve(id=gbid)
            db.Movies.insert_one(media.copy()) #copy keeps JSON serializeable
            logging.info('movie added: ' + media['title'])
        logging.info('movie db/api request time: ' + str(time.time() - start))
        print 'movie db/api request time: ', time.time() - start

        # add display sources to the movie detail dict
        media = add_src_display(media, 'movie')

    elif qtype == 'show':
        # get show query results, and take top result
        results = guidebox.Search.shows(field='title', query=query)
        if not (results['total_results'] > 0):  # exit early if no results
            return render_template('index.html', isresult=0,
                                   query=query, qtype=qtype)
        gbid = results['results'][0]['id']  # take first result

        # get show details from mongodb, or api search and add to mongodb
        media = db.Shows.find_one({'id': gbid})
        if not media:
            media = get_all_ep(gbid)
            db.Shows.insert_one(media.copy()) #copy keeps JSON serializeable
            logging.info('show added: ' + media['title'])
        logging.info('show db/api request time: ' + str(time.time() - start))
        print 'show db/api request time: ', time.time() - start

        # add display sources to the show_ep dict
        media = add_src_display(media, 'show')

        # append result high-level info to show_ep dict, not in all db docs
        m = results['results'][0]
        media['year'] =  m['first_aired'][:4]
        media['imdb'] = m['imdb_id']
        media['img'] =  m['artwork_208x117']

    # build other_results to send to template
    other_results = []
    for m in results['results'][1:5]:
        q_percent_enc = urllib.quote(m['title'].encode('utf-8'))
        x = {'link': 'search?q=' + q_percent_enc + '&type=' + qtype,
             'title': m['title']}
        # if (m['wikipedia_id'] != 0) and (m['wikipedia_id'] is not None):
        other_results.append(x)  # only keep if not very obscure

    # logs dictionaries retrieved, either from db or api
    logResults = open('log/search_results.log', 'w')
    pprint.pprint(results, logResults)
    logResults.close()
    logMedia = open('log/media_detail.log', 'w')
    pprint.pprint(media, logMedia)
    logMedia.close()

    return render_template('index.html', media=media, query=query,
                           qtype=qtype, other_results=other_results)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8181)
