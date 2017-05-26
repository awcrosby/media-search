#!/usr/bin/env python
import json
import guidebox


def get_all_ep(gbid):
    guidebox.api_key = json.loads(open('/home/awcrosby/media-search/'
                                  'apikeys.json').read())['guidebox']
    # get high-level show info
    show = guidebox.Show.retrieve(id=gbid)

    # get dictionary with many episodes
    page_len = 100
    episodes = guidebox.Show.episodes(id=gbid, include_links=True,
                                      limit=page_len)

    # get more pages of ep, only if results are greater than page_len
    for i in range(1, episodes['total_results']/page_len + 1):
        nextpage = guidebox.Show.episodes(id=gbid, include_links=True,
                                          limit=page_len,
                                          offset=page_len*i)
        episodes['results'] += nextpage['results']

    # add high-level show info to dict with all episodes
    episodes['id'] = gbid  # add a key to dictionary to allow lookup
    episodes['imdb_id'] = show['imdb_id']
    episodes['title'] = show['title']
    episodes['first_aired'] = show['first_aired']
    episodes['img'] = show['artwork_208x117']

    return episodes
