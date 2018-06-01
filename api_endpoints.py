#!/usr/bin/env python
# -*- coding: utf-8 -*-
# api_endpoints.py

# REST-like api for media_search

from flask_restful import Resource

class WatchlistAPI(Resource):
    decorators = [is_logged_in]

    def get(self):  # executed only by unit test
        user = db.Users.find_one({'email': session['email']})
        if not user:
            return '', 404
        return user['watchlist'], 200

    def post(self):  # executed via full browser request, not js
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


class UserAPI(Resource):
    def post(self):
        args = request.get_json()
        db.Users.find_one_and_update(
            {'email': session['email']},
            {'$set': {'prefs': {'hideAmzPayIcons': args['hideAmzPayIcons'],
                                'hideBlankLines': args['hideBlankLines']}}})
        return '', 204


class ItemAPI(Resource):
    def delete(self, mtype, mid):  # executed via javascript
        resp = db.Users.find_one_and_update(
            {'email': session['email']},
            {'$pull': {'watchlist': {'mtype': mtype, 'id': mid}}})
        if resp:
            return '', 204
        else:
            return 'Item was not deleted', 500


# set up api resource routing
api.add_resource(WatchlistAPI, '/api/watchlist')
api.add_resource(UserAPI, '/api/user')
api.add_resource(ItemAPI, '/api/item/<mtype>/<int:mid>')
