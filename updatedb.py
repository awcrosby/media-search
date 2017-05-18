#!/usr/bin/env python
import json
import guidebox
import requests
import pymongo

'''make popular lists of shows and movies, top 100-500 each
   (later update/append list)
   note if want to store all, in 1 week: changed movies 9k, changed ep 2k'''


if __name__ == "__main__":
    # connect to mongodb
    client = pymongo.MongoClient('localhost', 27017)
    db = client.MediaData

    # one-time db statements
    # print db.Shows.delete_many({})
    # print db.Movies.delete_many({})

    # get list of most popular movies
    guidebox.api_key = json.loads(open('apikeys.json').read())['guidebox']
    movies = guidebox.Movie.list(limit=5)
    for m in movies['results']:
        # get movie detail
        mov_detail = guidebox.Movie.retrieve(id=m['id'])

        # add to mongodb
        db.Movies.insert_one(mov_detail)


# make request for each media on popular lists

# twice daily get update lists of media with updates: new, changes, new ep, chg ep (later del)

# take intersection of update lists and popular lists, and make req for each item

# later periodically purge db items not on popular lists, or maintain all db items (since they will grow with new searches that are written to db, and popular list changing items)
