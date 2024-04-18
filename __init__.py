import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import json
from instructscore_visualizer.utils import convert_log_to_json, create_and_exec_slurm

from flask import Flask, render_template, request

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__)

    @app.route('/')
    def index():
        return render_template('index.html', title='InstructScore Visualizer', text='Please enter the path to Simuleval Output', placeholder='/mnt/data/...')
    
    @app.route('/process', methods=['POST'])
    def process_log_input():
        file = request.form['user_input']
        tgt = request.form['target_lang']
        src = request.form['source_lang']
        name = request.form['memorable_name']
        email = request.form['email']
        new_file=convert_log_to_json(file, src, tgt, name)
        create_and_exec_slurm(name, new_file, email)
        return render_template('log_output.html', memorable_name=name, file_name=new_file)
    
    @app.route('/log_input', methods=['GET'])
    def log_input():
        return render_template('log_input.html')
    
    @app.route('/instruct_out', methods=['GET'])
    def instruct_in():
        return render_template('instruct_in.html')
    
    @app.route('/visualize_instruct', methods=['POST'])
    def visualize_instruct():
        file = request.form['file']
        input_data = ("I want to display text", "display", "red")
        return render_template('visualize_instruct.html', input_data=input_data)
    
    
    
    
    return app