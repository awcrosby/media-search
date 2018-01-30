#!/usr/bin/env python
# -*- coding: utf-8 -*-
# config.py
"""Template configuration for Flask app, copy to root of project"""


class Config(object):
    DEBUG = False
    TESTING = False
    SECRET_KEY = 'this-key-should-be-changed'
    MONGO_URI = 'mongodb://localhost:27017/'
