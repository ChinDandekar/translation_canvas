import os

from flask import Flask

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__)

    @app.route('/')
    def hello():
        return 'Hello, World!'
    
    return app