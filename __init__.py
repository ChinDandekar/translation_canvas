
import os
import sys
import numpy as np
import pandas as pd
import json
from instructscore_visualizer.utils import convert_log_to_json, create_and_exec_slurm, instructscore_to_dict

from flask import Flask, render_template, request

path_to_file = os.path.dirname(os.path.abspath(__file__))
sys.path.append(path_to_file)
# Define the number of items per page
ITEMS_PER_PAGE = 5
help_text_json = json.load(open(os.path.join(path_to_file, 'help_text.json')))


def create_app(test_config=None):
    """
    Create and configure the Flask app.

    Args:
        test_config (dict, optional): Configuration dictionary for testing. Defaults to None.

    Returns:
        Flask: The configured Flask app.
    """
    app = Flask(__name__)

    @app.route('/')
    def index():
        """
        Render the index.html template.

        Returns:
            str: The rendered HTML template.
        """
        help_text = help_text_json["index"]
        return render_template('index.html', title='InstructScore Visualizer', help_text=help_text)
    
    @app.route('/process', methods=['POST'])
    def process_log_input():
        """
        Process the log input from the user.

        Returns:
            str: The rendered HTML template.
        """
        file = request.form['file']
        tgt = request.form['target_lang']
        src = request.form['source_lang']
        name = request.form['memorable_name']
        email = request.form['email']
        new_file=convert_log_to_json(file, src, tgt, name)
        create_and_exec_slurm(name, new_file, email)
        help_text = help_text_json["process_log_input"]
        return render_template('log_output.html', memorable_name=name, file_name=new_file, help_text=help_text)
    
    @app.route('/log_input', methods=['GET'])
    def log_input():
        """
        Render the log_input.html template.

        Returns:
            str: The rendered HTML template.
        """
        help_text = help_text_json["log_input"]
        source_languages = ['zh', 'en']
        target_languages = {
            'zh': ['en'],
            'en': ['es', 'ru', 'de']
        }
        language_names = {
        'zh': 'Chinese',
        'en': 'English',
        'es': 'Spanish',
        'ru': 'Russian',
        'de': 'German'
    }
        return render_template('log_input.html', help_text=help_text, source_languages=source_languages, 
                               target_languages=target_languages, 
                               language_names=language_names)
    
    @app.route('/instruct_in', methods=['GET'])
    def instruct_in():
        """
        Render the instruct_in.html template.

        Returns:
            str: The rendered HTML template.
        """
        help_text = help_text_json["instruct_in"]
        return render_template('instruct_in.html', help_text=help_text)
    
    @app.route('/visualize_instruct', methods=['POST','GET'])
    def visualize_instruct():
        """
        Visualize the instruct score.

        Returns:
            str: The rendered HTML template.
        """
        # Get page number from the request, default to 1 if not provided
        file = request.form['file']
        file_path = f"{path_to_file}/jobs/{file}/{file}_instructscore.json"
        print(file_path)
        if os.path.exists(file_path):

            page_number = int(request.form.get('current_page', 1))
            
            # Calculate the starting index based on the page number
            start_index = (page_number - 1) * ITEMS_PER_PAGE
            file = request.form['file']
            input_data, total_items, num_errors, most_common_errors, avg_errors, se_score = instructscore_to_dict(file, start_index, ITEMS_PER_PAGE)
        
            # Calculate total number of pages
            total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
            help_text = help_text_json["visualize_instruct"]
            return render_template('visualize_instruct.html', input_data=input_data, help_text=help_text, total_pages=total_pages, current_page=page_number, file=file, num_errors=num_errors, most_common_errors=most_common_errors, avg_errors=avg_errors, se_score=se_score)
        
        else:
            return render_template('error.html', error_message="File not found")
    
    return app