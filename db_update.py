#!/usr/bin/env python
import json
import guidebox
import pymongo
import time
import logging
import sys
from shared_func import get_show_ep, get_all_ep

'''db_update.py script populates and updates database daily
    add to mongo database any new top-popular shows and movies
    update any media inside database that has experienced an update'''


def main():
    # connect to mongodb, prepare api key, set logging config
    client = pymongo.MongoClient('localhost', 27017)
    db = client.MediaData
    guidebox.api_key = json.loads(open('/home/awcrosby/media-search/'
                                  'apikeys.json').read())['guidebox']
    time_ago = int(time.time() - 612000)  # week and 2hr ago
    logging.basicConfig(filename='/home/awcrosby/media-search/'
                        'log/db_update.log',
                        format='%(asctime)s %(levelname)s: %(message)s',
                        level=logging.INFO)
    sys.stdout = open('/home/awcrosby/media-search/log/db_update.log', 'a')
    print 'before api requests:'
    guidebox.Quota.retrieve()
    mv_new, mv_to_update, sh_new, sh_to_update = ([], [], [], [])

    ''' one-time db statements: create/view indexes, del all docs in col '''
    # db.Movies.create_index([('id', pymongo.ASCENDING)], unique=True)
    # db.Shows.create_index([('id', pymongo.ASCENDING)], unique=True)
    # db.Users.create_index('email', unique=True)
    # print sorted(list(db.Shows.index_information()))
    # print db.Shows.delete_many({})  # delete all shows in database
    # print db.Movies.delete_many({})  # delete all movies in database
    # import q; q.d()

    ''' Section for movies '''
    # get list of new popular movies to add to database
    mov_limit = 200
    page_len = 100
    mv_pop = guidebox.Movie.list(limit=page_len)  # initial dictionary
    for i in range(1, mov_limit/page_len):  # more pages if needed
        nextpage = guidebox.Movie.list(limit=page_len, offset=page_len*i)
        mv_pop['results'] += nextpage['results']
    mv_pop = [m['id'] for m in mv_pop['results']]
    mv_db = [m['id'] for m in db.Movies.find()]
    mv_new = list(set(mv_pop) - set(mv_db))

    # for all new movies get guidebox info and write to mongodb
    for gbid in mv_new:
        mov_detail = guidebox.Movie.retrieve(id=gbid)
        db.Movies.insert_one(mov_detail)
        logging.info('movie added: ' + mov_detail['title'])

    # get movie ids with updates / to update
    mv_chg = get_updates(obj='movie', typ='changes', time=time_ago)
    mv_chg = [m['id'] for m in mv_chg['results']]
    mv_db = [m['id'] for m in db.Movies.find()]
    mv_to_update = list(set(mv_chg) & set(mv_db))

    # del from mongodb and replace movies that have updates
    for gbid in mv_to_update:
        db.Movies.remove({'id': gbid})
        mov_detail = guidebox.Movie.retrieve(id=gbid)
        db.Movies.insert_one(mov_detail)
        logging.info('movie updated: ' + mov_detail['title'])

    ''' Section for shows '''
    # get list of new popular movies to add to database
    show_limit = 200
    page_len = 100
    sh_pop = guidebox.Show.list(limit=page_len)  # initial dictionary
    for i in range(1, show_limit/page_len):  # more pages if needed
        nextpage = guidebox.Show.list(limit=page_len, offset=page_len*i)
        sh_pop['results'] += nextpage['results']
    sh_pop = [m['id'] for m in sh_pop['results']]
    sh_db = [s['id'] for s in db.Shows.find()]
    sh_new = list(set(sh_pop) - set(sh_db))

    # for all new shows get guidebox episodes and write to mongodb
    for gbid in sh_new:
        show_ep = get_show_ep(gbid)
        db.Shows.insert_one(show_ep)
        logging.info('show added: ' + show_ep['title'])

    # get show ids with updates (show changes, changed ep, new ep) / to update
    sh_chgep = get_updates(obj='show', typ='changed_episodes', time=time_ago)
    sh_chgep = [e['id'] for e in sh_chgep['results']]
    sh_newep = get_updates(obj='show', typ='new_episodes', time=time_ago)
    sh_newep = [e['id'] for e in sh_newep['results']]
    sh_updated = list(set(sh_chgep + sh_newep))
    sh_db = [s['id'] for s in db.Shows.find()]
    sh_to_update = list(set(sh_updated) & set(sh_db))

    # update episode portion of show_episode dictionary
    for gbid in sh_to_update:
        show_ep_db = db.Shows.find_one({'id': gbid})
        episodes = get_all_ep(gbid)

        # add show info to the episodes
        episodes['id'] = gbid
        episodes['imdb_id'] = show_ep_db['imdb_id']
        episodes['title'] = show_ep_db['title']
        episodes['year'] = show_ep_db['year']
        episodes['img'] = show_ep_db['img']

        # update the show_episode dict in the database
        db.Shows.update_one({'id': gbid}, {'$set': episodes})
        logging.info('show updated: ' + show_ep_db['title'])

    # log database counts
    logging.info('movies added: ' + str(len(mv_new)))
    logging.info('movies updated: ' + str(len(mv_to_update)))
    logging.info('shows added: ' + str(len(sh_new)))
    logging.info('shows updated: ' + str(len(sh_to_update)))
    print 'after api requests:'
    guidebox.Quota.retrieve()
    sys.stdout.close()
    logging.info('database counts - movies: ' + str(db.Movies.count()) +
                 ', shows: ' + str(db.Shows.count()))


def get_updates(obj, typ, time):
    page_len = 500
    updates = guidebox.Update.all(object=obj, type=typ,
                                  time=time, limit=page_len)
    for i in range(1, updates['total_pages']):  # get extra pages if pages > 1
        nextpage = guidebox.Update.all(object=obj, type=typ,
                                       time=time, limit=page_len,
                                       offset=page_len*i)
        updates['results'] += nextpage['results']  # append to results
    return updates


if __name__ == "__main__":
    main()
