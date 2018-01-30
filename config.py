#!/usr/bin/env python
# -*- coding: utf-8 -*-
# config.py
"""Configuration for Flask app"""


class Config(object):
    DEBUG = False
    TESTING = False
    SECRET_KEY = 'this-key-should-be-changed'
    MONGO_URI = 'mongodb://localhost:27017/'
