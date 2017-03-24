#!/usr/bin/env python
from flask import Flask, render_template
from flask import request, redirect
from mediasearch import mediasearch
app = Flask(__name__)
results = []

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/result', methods = ['POST'])
def displayresults():
    query = request.form['movieq']
    qtype = 'movie'
    sources = mediasearch(query, qtype)
    if sources:
        display = 'The %s %s is available on these streaming services' % (qtype, query)
    else:
        display = 'The %s %s doesn\'t seem available on these streaming services' % (qtype, query)
    return render_template('index.html', display=display, sources=sources)

if __name__ == "__main__":
  app.run(host='0.0.0.0', port=8181)
