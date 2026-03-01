from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "FLASK IS RUNNING"

@app.route("/stats")
def stats():
    return {"status": "ok"}