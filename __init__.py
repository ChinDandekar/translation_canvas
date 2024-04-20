import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import json
from instructscore_visualizer.utils import convert_log_to_json, create_and_exec_slurm, instructscore_to_dict

from flask import Flask, render_template, request

# Define the number of items per page
ITEMS_PER_PAGE = 5

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
        help_text = {"This is the help button.\n Hover over it to see the help text for every page.": "None"}
        return render_template('index.html', title='InstructScore Visualizer', help_text=help_text)
    
    @app.route('/process', methods=['POST'])
    def process_log_input():
        """
        Process the log input from the user.

        Returns:
            str: The rendered HTML template.
        """
        file = request.form['user_input']
        tgt = request.form['target_lang']
        src = request.form['source_lang']
        name = request.form['memorable_name']
        email = request.form['email']
        new_file=convert_log_to_json(file, src, tgt, name)
        create_and_exec_slurm(name, new_file, email)
        help_text = {
            "Make sure to remember your memorable name, this is how you will access your results. You will receive an email when your results are ready.": "None"
        }
        return render_template('log_output.html', memorable_name=name, file_name=new_file, help_text=help_text)
    
    @app.route('/log_input', methods=['GET'])
    def log_input():
        """
        Render the log_input.html template.

        Returns:
            str: The rendered HTML template.
        """
        help_text = {
            "Make sure that the file is in the correct format.\n The file should be a .log file. Also make sure to use a descriptive and memorable name here (one that you can remember for at least 50 minutes). ": "None"
                     }
        return render_template('log_input.html', help_text=help_text)
    
    @app.route('/instruct_out', methods=['GET'])
    def instruct_in():
        """
        Render the instruct_in.html template.

        Returns:
            str: The rendered HTML template.
        """
        help_text = {
            "I hope you remembered the name you had assigned! If not, you can find it in your email, search for an email saying something like Slurm Job_id=(Some number) Name=(Your memorable name) has finished.": "None"
        }
        return render_template('instruct_in.html', help_text=help_text)
    
    @app.route('/visualize_instruct', methods=['POST','GET'])
    def visualize_instruct():
        """
        Visualize the instruct score.

        Returns:
            str: The rendered HTML template.
        """
        # Get page number from the request, default to 1 if not provided
        page_number = int(request.form.get('current_page', 1))
        
        # Calculate the starting index based on the page number
        start_index = (page_number - 1) * ITEMS_PER_PAGE
        file = request.form['file']
        input_data, total_items = instructscore_to_dict(file, start_index, ITEMS_PER_PAGE)
    
        # Calculate total number of pages
        total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        help_text = {
            'Each block contains a prediction and reference pair. The': "None",
            'red text': "red-text",
            'is major errors and ': "None",
            'orange text': "orange-text",
            'are minor errors. Put your mouse over the colored text to see more details about the error.': "None"
        }
        return render_template('visualize_instruct.html', input_data=input_data, help_text=help_text, total_pages=total_pages, current_page=page_number, file=file)
    
    return app