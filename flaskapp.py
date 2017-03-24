#!/usr/bin/env python
from flask import Flask, render_template
from flask import request, redirect
from mediasearch import mediasearch
app = Flask(__name__)
results = []

@app.route('/')
def home():
    return render_template('index.html', display="")

@app.route('/result', methods = ['POST'])
def displayresults():
    movieq = request.form['movieq']
    result = mediasearch(movieq)
    display = "You can stream on: %s" % result
    return render_template('index.html', display=display)

if __name__ == "__main__":
  app.run(host='0.0.0.0', port=8181)
