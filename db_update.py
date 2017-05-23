#!/usr/bin/env python
import json
import guidebox
import requests
import pymongo
import time
import math
from show_episodes import get_all_ep

'''make popular lists of shows and movies, top 100-500 each
   (later update/append list)
   note: if tried to store all, in 1 week: changed movies 9k, changed ep 2k'''


def main():
    # connect to mongodb, prepare api key
    client = pymongo.MongoClient('localhost', 27017)
    db = client.MediaData
    guidebox.api_key = json.loads(open('apikeys.json').read())['guidebox']
    halfday_ago = int(time.time() - 46800)  # 13 hours ago to ensure overlap

    ''' one-time db statements: create/view indexes, del all docs in col '''
    # db.Movies.create_index([('id', pymongo.ASCENDING)], unique=True)
    # db.Shows.create_index([('id', pymongo.ASCENDING)], unique=True)
    # print sorted(list(db.Shows.index_information()))
    # print db.Shows.delete_many({})  # delete all shows in database
    # print db.Movies.delete_many({})  # delete all movies in database
    print db.Movies.count(), db.Shows.count(), '... movies, shows in mongodb'

    # get list of movies to maintain, from guidebox popular and mongodb
    gb_mov = guidebox.Movie.list(limit=20)
    gb_id = [ m['id'] for m in gb_mov['results'] ]
    mon_id = [ m['id'] for m in db.Movies.find() ]
    new_id = list(set(gb_id) - set(mon_id))

    '''# for all new movies get guidebox info and write to mongodb
    for gbid in new_id:
        mov_detail = guidebox.Movie.retrieve(id=gbid)
        db.Movies.insert_one(mov_detail)
        print 'new movie inserted: ', mov_detail['title']'''

    # get list of movies to update, based on guidebox updates and mongodb
    page_len = 500
    changes = guidebox.Update.all(object='movie', type='changes',
                                  time=halfday_ago, limit=page_len)
    for i in range(1, changes['total_pages']):  # get extra pages if pages > 1
        nextpage = guidebox.Update.all(object='movie', type='changes',
                                       time=halfday_ago, limit=page_len,
                                       offset=page_len*i)
        changes['results'] += nextpage['results']  # append to results
    chg_id = [ m['id'] for m in changes['results'] ]
    mon_id = [ m['id'] for m in db.Movies.find() ]
    to_update_id = list(set(chg_id) & set(mon_id))  # takes set intersection

    '''# del from mongodb and replace movies that have updates
    for i in to_update_id:
        db.Movies.remove( {'id': i} )
        mov_detail = guidebox.Movie.retrieve(id=i)
        db.Movies.insert_one(mov_detail)
        print 'movie updated: ', mov_detail['title']
    print 'db movie count: ', db.Movies.count()'''

    ''' Section for shows '''
    # get list of shows to maintain, from guidebox popular and mongodb
    gb_show = guidebox.Show.list(limit=10)
    gb_id = [ m['id'] for m in gb_show['results'] ]
    mon_id = [ m['id'] for m in db.Shows.find() ]
    new_id = list(set(gb_id) - set(mon_id))

    # for all new shows get guidebox episodes and write to mongodb
    for gbid in new_id:
        show_ep = get_all_ep(gbid)
        db.Shows.insert_one(show_ep)
        print 'new show inserted: ', show_ep['title']

    # get list of all show ids updated, and ids to update
    changes = get_updates(media='show', update='changes', time=halfday_ago)
    new_ep = get_updates(media='show', update='new_episodes', time=halfday_ago)
    changed_ep = get_updates(media='show', update='changed_episodes',
                             time=halfday_ago)
    
    chg_id = [ m['id'] for m in changes['results'] ]
    newep_id = [ m['id'] for m in new_ep['results'] ]
    chgep_id = [ m['id'] for m in changed_ep['results'] ]
    updated_id = list(set(chg_id + newep_id + chgep_id))  # unique items

    mon_id = [ m['id'] for m in db.Movies.find() ]  #ids in mongodb
    to_update_id = list(set(updated_id) & set(mon_id))  # set intersection

    # del from mongodb and replace shows that have updates

    import q; q.d()

def get_updates( media, update, time ):
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
