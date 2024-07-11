
import os
import subprocess
import sys
import json
from instructscore_visualizer.utils import create_and_exec_slurm, instructscore_to_dict, read_file_content, write_file_content, get_completed_jobs

from flask import Flask, render_template, request, session
import secrets
import rocher.flask
import glob
from werkzeug.utils import secure_filename

path_to_file = os.path.dirname(os.path.abspath(__file__))
sys.path.append(path_to_file)
# Define the number of items per page
ITEMS_PER_PAGE = 5
help_text_json = json.load(open(os.path.join(path_to_file, 'help_text.json')))
UPLOAD_FOLDER = os.path.join(path_to_file, "uploaded_files")  # Specify your upload folder path
SCRIPTS_BASEPATH = os.path.join(path_to_file, "file_extraction_scripts")  # Specify your flaskcode resource basepath
extra_files = glob.glob(os.path.join(path_to_file, "file_extraction_scripts", "*.py")) 


def create_app(test_config=None):
    """
    Create and configure the Flask app.

    Args:
        test_config (dict, optional): Configuration dictionary for testing. Defaults to None.

    Returns:
        Flask: The configured Flask app.
    """
    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['SECRET_KEY'] = secrets.token_hex(16)
    rocher.flask.editor_register(app)

    @app.route('/')
    def index():
        """
        Render the index.j2 template.

        Returns:
            str: The rendered HTML template.
        """
        help_text = help_text_json["index"]
        return render_template('index.j2', title='InstructScore Visualizer', help_text=help_text)
    
    @app.route('/process', methods=['POST'])
    def process_input_form():
        """
        Process the log input from the user.

        Returns:
            str: The rendered HTML template.
        """
        
        filename = session['step1_data']['file']
        tgt = request.form['target_lang']
        src = request.form['source_lang']
        memorable_name = session['step1_data']['memorable_name']
        new_file = os.path.join(path_to_file, 'jobs', memorable_name, f'{memorable_name}_extracted.json')
        create_and_exec_slurm(memorable_name, new_file)
        help_text = help_text_json["process_input_form"]
        return render_template('log_output.j2', memorable_name=memorable_name, file_name=new_file, help_text=help_text)
    
    @app.route('/input_form/step1', methods=['GET', 'POST'])
    def file_input():
        """
        Render the file_input.j2 template.

        Returns:
            str: The rendered HTML template.
        """
        help_text = help_text_json["file_input"]
        
        if request.method == 'POST':
            
            if 'file_data' in request.form:
                filename = request.form[1]['file']
                file_type = request.form[1]['file_options']    
                
            elif 'file_upload' in request.files and request.files['file_upload'].filename != '':
                file = request.files['file_upload']
                filename = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
                file.save(filename)
                file_type = request.form['file_options']
                
            else:
                filename = request.form['file']
                if not os.path.exists(filename):
                    render_template("error.j2", error_message="File not found")
                file_type = request.form['file_options']
            
            memorable_name = request.form['memorable_name']
            source_code = read_file_content(os.path.join(path_to_file, 'file_extraction_scripts', f'extract_pairs_from_{file_type}.py'))
            file_content = read_file_content(filename)
            return render_template('editor.j2', source_code=source_code, file_content=file_content, file_type=file_type, memorable_name=memorable_name, filename=filename, help_text=help_text)
        
        file_options = {
            "JSON (.json)": "json",
            "SimulEval output (.log)": "log",
            "CSV (.csv)": "csv",
            "TSV (.tsv)": "tsv",
            "XML (.xml)": "xml",
            "None of the above ": "txt",
            }
        return render_template('file_input.j2', help_text=help_text, file_options=file_options)
    
    @app.route('/input_form/step2', methods=['POST'])
    def preview_pairs():
        """
        Preview the extracted pairs from the log file.

        Returns:
            str: The rendered HTML template.
        """
        
        source_code = request.form['source_code']
        file_type = request.form['file_options']
        filename = request.form['file']
        memorable_name = request.form['memorable_name']
        write_file_content(os.path.join(path_to_file, 'file_extraction_scripts', f'extract_pairs_from_{file_type}.py'), source_code)
        results = subprocess.run([sys.executable, os.path.join(path_to_file, 'file_to_json.py'), 
                        '--file_name', filename, '--memorable_name', memorable_name, '--file_type', file_type],
                        cwd=path_to_file,
                        capture_output=True,
                        text=True)
        
        if os.path.exists(os.path.join(path_to_file, 'jobs', memorable_name, f'{memorable_name}_extracted.json')):
            pairs = read_file_content(os.path.join(path_to_file, 'jobs', memorable_name, f'{memorable_name}_extracted.json'))
            file_content = read_file_content(filename)
            help_text = help_text_json["preview_pairs_success"]
            
            return render_template('preview_pairs_success.j2', pairs=pairs, source_code = source_code, file_type=file_type, filename=filename, memorable_name=memorable_name, file_content=file_content, help_text=help_text, err=results.stderr, out = results.stdout)
        else:
            file_content = read_file_content(filename)
            help_text = help_text_json["preview_pairs_failure"]
            return render_template('preview_pairs_failure.j2', source_code=source_code, file_type=file_type, filename=filename, memorable_name=memorable_name, file_content=file_content, err=results.stderr, out = results.stdout, help_text=help_text)
        # if os.path.exists(file_path):
        #     pairs = json.load(open(file_path))
        #     help_text = help_text_json["preview_pairs"]
        #     return render_template('preview_pairs.j2', pairs=pairs, help_text=help_text, file=file)
        # else:
        #     return render_template('error.j2', error_message="File not found")
    
    
    @app.route('/input_form/step3', methods=['POST'])
    def input_form():
        """
        Render the input_form.j2 template.

        Returns:
            str: The rendered HTML template.
        """
        session['step1_data'] = request.form
        help_text = help_text_json["input_form"]
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
        return render_template('input_form.j2', help_text=help_text, source_languages=source_languages, 
                               target_languages=target_languages, 
                               language_names=language_names)
    
    @app.route('/instruct_in', methods=['GET'])
    def instruct_in():
        """
        Render the instruct_in.j2 template.

        Returns:
            str: The rendered HTML template.
        """
        options = get_completed_jobs()
        help_text = help_text_json["instruct_in"]
        return render_template('instruct_in.j2', help_text=help_text, options=options)
    
    @app.route('/visualize_instruct', methods=['POST','GET'])
    def visualize_instruct():
        """
        Visualize the instruct score.

        Returns:
            str: The rendered HTML template.
        """
        # Get page number from the request, default to 1 if not provided
        if 'files' in request.form:
            files = request.form.getlist('files')
            print(f"files fom next page: {files}")
        else:
            files = request.form.getlist('selected_options')
        
        input_data = []
        
                    
        page_number = int(request.form.get('current_page', 1))
        
        # Calculate the starting index based on the page number
        start_index = (page_number - 1) * ITEMS_PER_PAGE
        
        print(f"{files} are the files")
        for file in files:
            data, total_items, num_errors, most_common_errors, avg_errors, se_score = instructscore_to_dict(file, start_index, ITEMS_PER_PAGE)
            for i,item in enumerate(data):
                if len(input_data) <= i:
                    input_data.append({'prediction': {}})
                input_data[i]['prediction'][file] = item['prediction']
                input_data[i]['reference'] = item['reference']
            
        

        print(input_data)            
        
        
        # Calculate total number of pages
        total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        help_text = help_text_json["visualize_instruct"]
            
        return render_template('visualize_instruct.j2', input_data=input_data, help_text=help_text, total_pages=total_pages, current_page=page_number, files=files, num_errors=num_errors, most_common_errors=most_common_errors, avg_errors=avg_errors, se_score=se_score)
    
    return app