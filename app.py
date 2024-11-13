
import os
import subprocess
import sys
import json
from translation_canvas.utils import read_file_content, write_file_content, spawn_independent_process, _delete_runs_subprocess, get_files_from_session_or_form, extract_search_configuration
from translation_canvas.readwrite_database import read_data, read_data_df
from translation_canvas.setup import setup_system
from translation_canvas.sql_queries import get_filename, construct_distribution_query, construct_full_search_query, construct_pred_text_query, error_type_distribution_query, get_scores, get_all_refs_query, get_instances_query
from translation_canvas.plotly_functions import create_histogram, create_radar_chart

from flask import Flask, render_template, request, session, jsonify, send_from_directory, redirect, url_for
import secrets
import rocher.flask
from werkzeug.utils import secure_filename

import plotly.utils
import pandas as pd
from datetime import datetime
import multiprocessing
from dotenv import load_dotenv

path_to_file = os.path.dirname(os.path.abspath(__file__))
sys.path.append(path_to_file)
# Define the number of items per page
ITEMS_PER_PAGE = 10
help_text_json = json.load(open(os.path.join(path_to_file, 'help_text.json')))
UPLOAD_FOLDER = os.path.join(path_to_file, "uploaded_files")  # Specify your upload folder path
SCRIPTS_BASEPATH = os.path.join(path_to_file, "file_extraction_scripts")  # Specify your flaskcode resource basepath
CUDA_DEVICES_FILE = os.path.join(path_to_file, "tmp", "cuda_devices.json")
logging = False
ranking_log = os.path.join(path_to_file, "tmp", "ranking.log")
if not os.path.exists(ranking_log):
    open(ranking_log, 'w').close()


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
    
    #create run_id_dict
    results = read_data("SELECT id, filename FROM runs;")
    run_id_dict = {result[0]: result[1] for result in results}

    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')
    
    @app.route('/')
    def index():
        """
        Render the index.j2 template.

        Returns:
            str: The rendered HTML template.
        """
        help_text = help_text_json["index"]
        if not os.path.exists(os.path.join(path_to_file, ".env")) or not os.path.exists(os.path.join(path_to_file, "translation_canvas.db")):
            return render_template('setup.j2',  title='Translation Canvas', help_text=help_text)
        
        
        # clean out session
        session.clear()
        runs = read_data("SELECT id, filename, source_lang, target_lang, in_progress, se_score, bleu_score, num_predictions, run_type, exit_status FROM runs ORDER BY target_lang, se_score, bleu_score DESC;", logging=logging)
        table_data = []
        for run in runs:
            se_score = round(float(run[5]), 3) if run[5] else 'N/A'
            bleu_score = round(float(run[6]), 3) if run[6] is not None else 'N/A'
            status = None
            run_type = run[8] if run[8] else 'no eval'
            
            if run[4] and run[4] > 0:
                if run[4] >= 1:
                    status = 'Completed'
                else:
                    status = f'{round(run[4]*100, 2)}%'
            else:
                status = 'Starting'
            
            if run[9] is not None and run[9] != 0:
                status = f"Error with status {run[9]}"
                    
            table_data.append({'id': run[0], 'filename': run[1], 'source_lang': run[2], 'target_lang': run[3], 'status': status, 'se_score': se_score, 'bleu_score': bleu_score, 'num_predictions': run[7], 'run_type': run_type})
                
        return render_template('index.j2', help_text=help_text, table_data=table_data)
    
    @app.route('/setup', methods=['GET', 'POST'])
    def setup():
        """
        Setup the environment for the app.

        Returns:
            str: The rendered HTML template.
        """
        if request.method == 'GET':
            help_text = help_text_json["get_system_info"]
            
            return render_template('get_system_info.j2', help_text=help_text)
        if request.method == 'POST':
            data = request.form
            gpu_ids = data.get('gpu_ids', None)
            cache_dir = data.get('cache_dir', None)
            file = open(os.path.join(path_to_file, ".env"), 'w')
            if gpu_ids:
                file.write(f"AVAILABLE_GPU_IDS={gpu_ids}\n")
            file.write(f"CACHE_DIR='{cache_dir}'\n")
            file.close()
            
            help_text = help_text_json["index"]
            return redirect(url_for('index'))
    
    @app.route('/process', methods=['POST'])
    def process_input_form():
        """
        Process the log input from the user.

        Returns:
            str: The rendered HTML template.
        """
        tgt = session['step1_data']['target_lang']
        src = session['step1_data']['source_lang']
        evaluation_type = session['step1_data']['evaluation_type']
        data_types = session['step1_data']['data_types']
        memorable_name = session['step1_data']['memorable_name']
        new_file = os.path.join(path_to_file, 'jobs', memorable_name, f'{memorable_name}_extracted.json')
        command = f"{sys.executable} {os.path.join(path_to_file, 'spawn_eval_and_monitor.py')} --run_name {memorable_name} --src_lang {src} --tgt_lang {tgt}"
        if session['step1_data']['input_method'] != 'file':
            data_dict = request.form.to_dict()
            extracted_data = []
            for i in range(len(data_dict)):
                if data_dict.get(f'prediction{i}', -1) != -1:
                    extracted_data.append({'prediction': data_dict[f'prediction{i}']})
                if data_dict.get(f'reference{i}', -1) != -1:
                    extracted_data[i]['reference'] = data_dict[f'reference{i}']
                if data_dict.get(f'source{i}', -1) != -1:
                    extracted_data[i]['source'] = data_dict[f'source{i}']
            
            if not os.path.exists(os.path.join(path_to_file, 'jobs', memorable_name)):
                os.mkdir(os.path.join(path_to_file, 'jobs', memorable_name))
                
            json.dump(extracted_data, open(new_file, 'w'), indent=4)
    
        if evaluation_type:
            if 'instructscore' in evaluation_type:
                command += " --instructscore True"
            if 'bleu' in evaluation_type:
                command += " --bleu True"  
            if 'comet' in evaluation_type:
                command += " --comet True"
        
        if data_types == 'ref':
            command += " --ref True"
        elif data_types == 'src':
            command += " --src True"
        else:
            command += " --ref True --src True"
        spawn_independent_process(command)
        help_text = help_text_json["process_input_form"]
        return render_template('log_output.j2', memorable_name=memorable_name, file_name=new_file, help_text=help_text)
    
    @app.route('/input_form/step1', methods=['GET', 'POST'])
    def basic_info():
        """
        Render the basic_info.j2 template.

        Returns:
            str: The rendered HTML template.
        """
        help_text = help_text_json["basic_info"]
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
        
        load_dotenv()
        available_gpus = os.getenv('AVAILABLE_GPU_IDS')
        available_gpus = available_gpus.split(',') if available_gpus else []
        
        return render_template('input_form.j2', help_text=help_text, source_languages=source_languages, 
                               target_languages=target_languages, 
                               language_names=language_names, available_gpus=available_gpus)
        
    
    @app.route('/input_form/editor', methods = ['POST'])
    def editor():
        help_text = help_text_json['editor']
        form_info = request.form
        if len(request.form) == 0:
            if 'step1_data' not in session:
                render_template('error.j2', error_message = "Form data has been lost.", method='POST', link='/input_form/step1', help_text = help_text_json['error'])
            else:
                form_info = session['step1_data']
                
            
        if 'file_data' in form_info:
            filename = form_info[1]['file']
            file_type = form_info[1]['file_options']    
            
        elif 'file_upload' in request.files and request.files['file_upload'].filename != '':
            file = request.files['file_upload']
            filename = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
            file.save(filename)
            file_type = form_info['file_options']
            
        else:
            filename = form_info['file']
            file_type = form_info['file_options']


        if not os.path.exists(filename):
            return render_template("error.j2", error_message="The file you specified does not exist. Please specify the file path of a valid file stored on the system that is running this webapp, or upload a file.",method="POST", link='/input_form/step2', help_text=help_text_json['error'])
        
        memorable_name = session['step1_data']['memorable_name']
        session['step1_data']['file'] = filename
        source_code = read_file_content(os.path.join(path_to_file, 'file_extraction_scripts', f'extract_pairs_from_{file_type}.py'))
        file_content = read_file_content(filename)
        return render_template('editor.j2', source_code=source_code, file_content=file_content, file_type=file_type, memorable_name=memorable_name, filename=filename, help_text=help_text)
    
    @app.route('/input_form/step2', methods=['POST'])
    def file_input():
        """
        Render the file_input.j2 template.

        Returns:
            str: The rendered HTML template.
        """
        help_text = help_text_json["file_input"]
        
        
        if 'gpus' in request.form:
            json.dump(request.form.getlist('gpus'), open(CUDA_DEVICES_FILE, 'w'), indent=4)
    
        
        form_info = request.form
        if 'step1_data' in session:
            form_info = session['step1_data']
        elif len(request.form) > 0:
            form_info = request.form.to_dict()
            session['step1_data'] = form_info
                
        
        if 'input_method' not in form_info:
            return render_template('error.j2', )
        
        if 'input_method' in form_info:
            data_types = form_info['data_types'] if 'data_types' in form_info else None
                
            src = False if data_types == 'ref' else True
            ref = False if data_types == 'src' else True
            
            accept_file_types = """
                .json,
                .log,
                .csv,
                .tsv,
                .xml,
                .txt 
            """
                
            if form_info['input_method'] == 'file':
                file_options = {
                    "JSON (.json)": "json",
                    "SimulEval output (.log)": "log",
                    "CSV (.csv)": "csv",
                    "TSV (.tsv)": "tsv",
                    "XML (.xml)": "xml",
                    "Text (.txt) ": "txt",
                    }
                return render_template('file_input.j2', help_text=help_text, file_options=file_options, accept_file_types = accept_file_types) 
            else:
            
                return render_template('manual_input.j2', help_text=help_text, src=src, ref=ref)
    
    @app.route('/input_form/step3', methods=['POST'])
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
        session['step1_data']['file'] = filename
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
    
    
    @app.route('/instruct_in', methods=['GET'])
    def instruct_in():
        """
        Render the instruct_in.j2 template.

        Returns:
            str: The rendered HTML template.
        """
        results = read_data("SELECT id, filename FROM runs WHERE in_progress > 0 ORDER BY se_score DESC;", logging=logging)
        options = {result[0]: result[1] for result in results } 
        help_text = help_text_json["instruct_in"]
        return render_template('instruct_in.j2', help_text=help_text, options=options)
    
    
    @app.route('/dashboard', methods=['GET', 'POST'])
    def dashboard():
        """
        Render the dashboard.j2 template.

        Returns:
            str: The rendered HTML template.
        """
        help_text = help_text_json["dashboard"]
        # collect counts of types of errors for each run
        if 'ids' in request.form:
            ids = request.form.get('ids', '[]')
            ids = tuple(json.loads(ids))
        elif 'files' in request.form:
            ids = tuple(request.form.getlist('files'))
        
        stats_dict = {}
        run_types = read_data(f"SELECT run_type FROM runs WHERE id IN {ids}", logging=logging)
        instructscore = False
        comet = False
        bleu = False
        for id, run_type in zip(ids, run_types):
            if 'i' in run_type[0]:
                if 'instruct' not in stats_dict:
                    stats_dict['instruct'] = []
                    instructscore = True
                stats_dict['instruct'].append(id)
            if 'c' in run_type[0]:
                if 'comet' not in stats_dict:
                    stats_dict['comet'] = []
                    comet = True
                stats_dict['comet'].append(id)
            if 'b' in run_type[0]:
                bleu = True
        
        categories = []

        instructscore_distribution_graph = None
        error_type_graph = None
        if 'instruct' in stats_dict:
            stats_dict['instruct'] = tuple(stats_dict['instruct'])
            categories.append('InstructScore')
            
            query = error_type_distribution_query(stats_dict)
            error_type_df = read_data_df(query, logging=logging)
            error_type_df['Run'] = error_type_df['run_id'].apply(get_filename)  # Add the run filename directly to the DataFrame

            query = construct_distribution_query('se_score', 'InstructScore', stats_dict['instruct'], precision=0)
            instructscore_distribution_df = read_data_df(query, logging=logging)
            instructscore_distribution_df['Run'] = instructscore_distribution_df['run_id'].apply(get_filename)
            
            error_type_graph = create_histogram(error_type_df, xaxis_title='Error Type', yaxis_title='Count', title='InstructScore: Frequency of types of errors')
            instructscore_distribution_graph = create_histogram(instructscore_distribution_df, xaxis_title='InstructScore', yaxis_title='Count', title='InstructScore: Distribution of scores per instance', ticks='outside')
                
                
        comet_distribution_graph = None
        if comet:
            stats_dict['comet'] = tuple(stats_dict['comet'])
            categories.append('COMET')
            
            query = construct_distribution_query('comet_score', 'CometScore', stats_dict['comet'])
            comet_distribution_df = read_data_df(query, logging=logging)
            comet_distribution_df['Run'] = comet_distribution_df['run_id'].apply(get_filename)
            # Calculate the bar width
            comet_distribution_graph = create_histogram(comet_distribution_df, xaxis_title='CometScore', yaxis_title='Count', title='COMET: Distribution of scores per instance', bar_width=None, ticks='outside')
                
        if bleu:
            categories.append('BLEU')
            

        query = get_scores(ids)
        scores_df = read_data_df(query, logging=logging)
        
        ranges = {
            "InstructScore": [-25, -2], # InstructScore
            "BLEU": [0, 48], # BLEU
            "COMET": [0, 0.9] # COMET
        }
        normalized_df = pd.DataFrame()
        for i, category in enumerate(categories):
            normalized_df[category] = scores_df[category].apply(lambda x: (x - ranges[category][0]) / (ranges[category][1] - ranges[category][0]))
        normalized_df['run_id'] = scores_df['run_id']
        scores_radar_chart = create_radar_chart(scores_df, normalized_df, categories)
        
        session['compare_systems_ids'] = ids
       
        return render_template('dashboard.j2', help_text=help_text, instructscore=instructscore, bleu=bleu, comet=comet, error_type_graph=error_type_graph, instructscore_distribution_graph=instructscore_distribution_graph, comet_distribution_graph=comet_distribution_graph, scores_radar_chart=scores_radar_chart) 


    @app.route('/visualize_instruct', methods=['POST','GET'])
    def visualize_instruct():
        """
        Visualize the instruct score.

        Returns:
            str: The rendered HTML template.
        """
        # Get page number from the request, default to 1 if not provided
        files = get_files_from_session_or_form(request, session)
        
        search_options, search_texts, search_query, conjunctions = extract_search_configuration(request, session)
        session['search_query'] = search_query
        session['search_options'] = search_options
        session['search_texts'] = search_texts
        session['conjunctions'] = conjunctions
        
        input_data = []
        page_number = int(request.form.get('current_page', 1))
        
        load_items_per_page = ITEMS_PER_PAGE//len(files)
        load_items_per_page = load_items_per_page if load_items_per_page >= 1 else 1
        
        # Calculate the starting index based on the page number
        start_index = (page_number - 1) * load_items_per_page
        
        # get ids for files selected
        run_ids = tuple(files)
        
        # first get all references used in the selected files
        read_query = get_all_refs_query(search_query, load_items_per_page, start_index, run_ids)
        total_items_query = (
                              f"SELECT COUNT( * ) FROM (SELECT DISTINCT ref_id, src_id FROM preds WHERE run_id IN {run_ids})  "
                            )
        if search_query:
            total_items_query = f"SELECT COUNT( * ) FROM (SELECT DISTINCT ref_id, src_id FROM preds WHERE run_id IN {run_ids} AND preds.id IN ({search_query}));"
        total_items = read_data(total_items_query, logging=logging)[0][0]
        
        results = read_data(read_query, logging=logging)
        ref_ids = tuple([result[0] for result in results])
        src_ids = tuple([result[1] for result in results])
        
        ref_ids_sql = f"({','.join([str(ref_id) for ref_id in ref_ids if ref_id])})"
        src_ids_sql = f"({','.join([str(src_id) for src_id in src_ids if src_id])})"
        input_data = {(result[0], result[1]): {'reference': result[3], 'runs' : {}, "source": result[2]} for result in results}       # use ref_id and src_id as a unique id for each instance
        read_query = get_instances_query(run_ids, ref_ids_sql, src_ids_sql)
        results = read_data(read_query, logging=logging)
        
        does_search_have_error = False
        if len(results) > 0:
            for option in search_options:
                if 'error' in option and not does_search_have_error:
                    pred_ids = tuple([result[6] for result in results])
                    preds_text_seach_query = construct_pred_text_query(search_options, search_texts, conjunctions, pred_ids)
                    preds_text_search_results = read_data(preds_text_seach_query, logging=logging)
                    pred_text_search_ids = tuple([pred_text[0] for pred_text in preds_text_search_results])
                    does_search_have_error = True
            
        for result in results:          
            cur_filename = result[4]
            key = (result[5], result[9])
            if key in input_data:
                if cur_filename not in input_data[key]['runs']:
                    input_data[key]['runs'][cur_filename] = {'prediction': {}}
                    input_data[key]['runs'][cur_filename]['pred_id'] = result[6]
                    input_data[key]['runs'][cur_filename]['se_score'] = result[7]
                    input_data[key]['runs'][cur_filename]['comet_score'] = round(result[8],2) if result[8] else None
                input_data[key]['runs'][cur_filename]['prediction'][result[0]] =  {"error_type": result[1], "error_scale": result[2], "error_explanation": result[3], "color": 'red' if result[2] == 'Major' else 'orange'} if result[1] else "None"
                if does_search_have_error:
                    if result[10] in pred_text_search_ids:
                        input_data[key]['runs'][cur_filename]['prediction'][result[0]]['color'] = 'blue'
                
        # Calculate total number of pages
        total_pages = (total_items + load_items_per_page - 1) // load_items_per_page
        help_text = help_text_json["visualize_instruct"]
        
        return render_template('visualize_instruct.j2', input_data=input_data, help_text=help_text, total_pages=total_pages, current_page=page_number, files=files, search_options=search_options, search_texts=search_texts, conjunctions=conjunctions)
    
    
    @app.route('/log', methods=['POST'])
    def log_ranking():
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        try: 
            if isinstance(request.data, bytes):
                data_str = request.data.decode('utf-8')
                data = json.loads(data_str)
            else:
                data = request.get_json()
            
            higher_pred_id = data.get('higherPredId')
            lower_pred_id = data.get('lowerPredId')
            
            with open(ranking_log, 'a') as f:
                f.write(f"{dt_string}: {higher_pred_id} > {lower_pred_id}\n")
            return jsonify({"status": "success", "message": "Log entry created"}), 200
    
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400
        
        
    @app.route('/delete_runs', methods=['POST'])
    def delete_runs():
        try: 
            if isinstance(request.data, bytes):
                data_str = request.data.decode('utf-8')
                data = json.loads(data_str)
            else:
                data = request.get_json()
            run_ids = [int(run_id) for run_id in data]
            
            # start a new process to delete the runs because database connection is in read mode currently
            process = multiprocessing.Process(target=_delete_runs_subprocess, args=(run_ids,))
            process.start()
            process.join()
            
            return jsonify({"status": "success", "message": f"Runs {run_ids} were deleted"}), 200
            
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    
    
    @app.route('/clear_search_cache', methods=['POST'])
    def clear_search_cache():
        if 'search_options' in session:
            del session['search_options']
        if 'search_texts' in session:
            del session['search_texts']
        if 'search_query' in session:
            del session['search_query']
        if 'conjunctions' in session:
            del session['conjunctions']
        return jsonify({"status": "success", "message": "Search cache cleared"}), 200


    return app