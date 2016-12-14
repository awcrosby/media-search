#!/usr/bin/env python
from flask import Flask, render_template
from flask import request, redirect
app = Flask(__name__)

@app.route("/")
def home():
	#import mediasearch
	movie = "test movie"
	nfr = "test netflix"
	gb = "test hulu and hbo"
	
	return render_template('index.html', movie=movie, nfr=nfr, gb=gb)

@app.route('/query', methods = ['POST'])
def query():
    movieq = request.form['movieq']
    print("The movie query is '" + movieq + "'")
    return redirect('/')	
	
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8888)