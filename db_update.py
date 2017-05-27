#!/usr/bin/env python
import json
import guidebox
import pymongo
import time
import logging
from shared_func import get_all_ep

'''db_update.py script populates and updates database daily
    add to mongo database any new top-popular shows and movies
    update any media inside database that has experienced an update'''


def main():
    # connect to mongodb, prepare api key, set logging config
    client = pymongo.MongoClient('localhost', 27017)
    db = client.MediaData
    guidebox.api_key = json.loads(open('/home/awcrosby/media-search/'
                                  'apikeys.json').read())['guidebox']
    halfday_ago = int(time.time() - 44100)  # 12hr 15min ago to ensure overlap
    logging.basicConfig(filename='/home/awcrosby/media-search/'
                        'log/db_update.log',
                        format='%(asctime)s %(levelname)s: %(message)s',
                        level=logging.INFO)

    ''' one-time db statements: create/view indexes, del all docs in col '''
    # db.Movies.create_index([('id', pymongo.ASCENDING)], unique=True)
    # db.Shows.create_index([('id', pymongo.ASCENDING)], unique=True)
    # print sorted(list(db.Shows.index_information()))
    # print db.Shows.delete_many({})  # delete all shows in database
    # print db.Movies.delete_many({})  # delete all movies in database
    # import q; q.d()

    # get initial dictionary with many guidebox popular movies
    mov_limit = 300
    page_len = 50
    gb_movs = guidebox.Movie.list(limit=page_len)

    # get the additional pages of popular movies
    for i in range(1, mov_limit/page_len):
        nextpage = guidebox.Movie.list(limit=page_len, offset=page_len*i)
        gb_movs['results'] += nextpage['results']

    # get list of new movie ids, based on popular and existing mongodb
    pop_ids = [m['id'] for m in gb_movs['results']]
    mon_ids = [m['id'] for m in db.Movies.find()]
    new_ids = list(set(pop_ids) - set(mon_ids))

    # for all new movies get guidebox info and write to mongodb
    for gbid in new_ids:
        mov_detail = guidebox.Movie.retrieve(id=gbid)
        db.Movies.insert_one(mov_detail)
        logging.info('movie added: ' + mov_detail['title'])

    # get list of movies to update, based on guidebox updates and mongodb
    chg = get_updates(media='movie', update='changes', time=halfday_ago)
    chg_ids = [m['id'] for m in chg['results']]
    mon_ids = [m['id'] for m in db.Movies.find()]
    to_update_ids = list(set(chg_ids) & set(mon_ids))  # takes set intersection

    # del from mongodb and replace movies that have updates
    for gbid in to_update_ids:
        db.Movies.remove({'id': gbid})
        mov_detail = guidebox.Movie.retrieve(id=gbid)
        db.Movies.insert_one(mov_detail)
        logging.info('movie updated: ' + mov_detail['title'])

    ''' Section for shows '''
    # get initial dictionary with many guidebox popular shows
    show_limit = 300
    page_len = 50
    gb_shows = guidebox.Show.list(limit=page_len)

    # get the additional pages of popular shows
    for i in range(1, show_limit/page_len):
        nextpage = guidebox.Show.list(limit=page_len, offset=page_len*i)
        gb_shows['results'] += nextpage['results']

    # get list of new show ids, based on popular and existing mongodb
    pop_ids = [m['id'] for m in gb_shows['results']]
    mon_ids = [m['id'] for m in db.Shows.find()]
    new_ids = list(set(pop_ids) - set(mon_ids))

    # for all new shows get guidebox episodes and write to mongodb
    for gbid in new_ids:
        show_ep = get_all_ep(gbid)
        db.Shows.insert_one(show_ep)
        logging.info('show added: ' + show_ep['title'])

    # get list of all show ids updated, and ids to update
    chg = get_updates(media='show', update='changes', time=halfday_ago)
    newep = get_updates(media='show', update='new_episodes', time=halfday_ago)
    chgep = get_updates(media='show', update='changed_episodes',
                        time=halfday_ago)

    chg_ids = [m['id'] for m in chg['results']]
    newep_ids = [m['id'] for m in newep['results']]
    chgep_ids = [m['id'] for m in chgep['results']]
    updated_ids = list(set(chg_ids + newep_ids + chgep_ids))  # unique items

    mon_ids = [m['id'] for m in db.Shows.find()]
    to_update_ids = list(set(updated_ids) & set(mon_ids))  # set intersection

    # del from mongodb and replace shows that have updates
    for gbid in to_update_ids:
        db.Shows.remove({'id': gbid})
        show_ep = get_all_ep(gbid=gbid)
        db.Shows.insert_one(show_ep)
        logging.info('show updated: ' + show_ep['title'])

    # log database counts
    logging.info('database counts - movies: ' + str(db.Movies.count()) +
                 ', shows: ' + str(db.Shows.count()))


def get_updates(media, update, time):
    page_len = 500
    updates = guidebox.Update.all(object=media, type=update,
                                  time=time, limit=page_len)
    for i in range(1, updates['total_pages']):  # get extra pages if pages > 1
        nextpage = guidebox.Update.all(object=media, type=update,
                                       time=time, limit=page_len,
                                       offset=page_len*i)
        updates['results'] += nextpage['results']  # append to results
    return updates


if __name__ == "__main__":
    main()
