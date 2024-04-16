import os

from flask import Flask, render_template, request

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__)

    @app.route('/')
    def index():
        return render_template('index.html', title='InstructScore Visualizer', text='../taurus/')
    
    @app.route('/process', methods=['POST'])
    def process_input():
        user_input = request.form['user_input']
        processed_input = user_input.upper()  # Example: Convert input to uppercase
        return render_template('result.html', processed_input=processed_input)
    
    return app