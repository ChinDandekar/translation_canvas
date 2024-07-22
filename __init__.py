
import os
import subprocess
import sys
import json
from instructscore_visualizer.utils import read_file_content, write_file_content, spawn_independent_process, kill_processes_by_run_id
from instructscore_visualizer.readwrite_database import read_data, write_data

from flask import Flask, render_template, request, session, jsonify, send_from_directory
import secrets
import rocher.flask
import glob
from werkzeug.utils import secure_filename

from datetime import datetime
import multiprocessing

path_to_file = os.path.dirname(os.path.abspath(__file__))
sys.path.append(path_to_file)
# Define the number of items per page
ITEMS_PER_PAGE = 10
help_text_json = json.load(open(os.path.join(path_to_file, 'help_text.json')))
UPLOAD_FOLDER = os.path.join(path_to_file, "uploaded_files")  # Specify your upload folder path
SCRIPTS_BASEPATH = os.path.join(path_to_file, "file_extraction_scripts")  # Specify your flaskcode resource basepath
extra_files = glob.glob(os.path.join(path_to_file, "file_extraction_scripts", "*.py")) 
logging = False
run_id_dict = {}
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
        if not os.path.exists(os.path.join(path_to_file, ".env")) or not os.path.exists(os.path.join(path_to_file, "temporary.db")):
            return render_template('setup.j2',  title='InstructScore Visualizer', help_text=help_text)
        help_text = help_text_json["index"]
        
        runs = write_data("SELECT id, filename, source_lang, target_lang, in_progress, se_score, num_predictions FROM runs ORDER BY se_score DESC;", logging=logging)
        table_data = []
        for run in runs:
            if run[4] > 0:
                table_data.append({'id': run[0], 'filename': run[1], 'source_lang': run[2], 'target_lang': run[3], 'status': run[4], 'se_score': round(float(run[5]), 3), 'num_predictions': run[6]})
                if run[4] > 1:
                    table_data[-1]['status'] = 'Completed'
                else:
                    table_data[-1]['status'] = f'{round(run[4]*100, 2)}%'
            else:
                table_data.append({'id': run[0], 'filename': run[1], 'source_lang': run[2], 'target_lang': run[3], 'status': 'Starting', 'se_score': 'N/A', 'num_predictions': 'N/A'})
                
        return render_template('index.j2', help_text=help_text, table_data=table_data)
    
    @app.route('/process', methods=['POST'])
    def process_input_form():
        """
        Process the log input from the user.

        Returns:
            str: The rendered HTML template.
        """
        print(f"session in process_input_form: {session}")
        print(f"process_input_form request.form: {request.form}")
        tgt = session['step1_data']['target_lang']
        src = session['step1_data']['source_lang']
        memorable_name = session['step1_data']['memorable_name']
        new_file = os.path.join(path_to_file, 'jobs', memorable_name, f'{memorable_name}_extracted.json')
        command = f"{sys.executable} {os.path.join(path_to_file, 'spawn_eval_and_monitor.py')} --run_name {memorable_name} --src_lang {src} --tgt_lang {tgt}"
        if session['step1_data']['input_type'] != 'file':
            data_dict = request.form.to_dict()
            extracted_data = []
            for i in range(len(data_dict)//2):
                if data_dict.get(f'prediction{i}', -1) != -1:
                    extracted_data.append({'prediction': data_dict[f'prediction{i}'], 'reference': data_dict[f'reference{i}']})
            
            if not os.path.exists(os.path.join(path_to_file, 'jobs', memorable_name)):
                os.mkdir(os.path.join(path_to_file, 'jobs', memorable_name))
                
            json.dump(extracted_data, open(new_file, 'w'), indent=4)
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
        
        
        return render_template('input_form.j2', help_text=help_text, source_languages=source_languages, 
                               target_languages=target_languages, 
                               language_names=language_names)
    
    @app.route('/input_form/step2', methods=['GET', 'POST'])
    def file_input():
        """
        Render the file_input.j2 template.

        Returns:
            str: The rendered HTML template.
        """
        help_text = help_text_json["file_input"]
        print(f"request.form: {request.form}, session: {session}")
        if 'file_options' in request.form:              # user has chosen a file type
            
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
            
            memorable_name = session['step1_data']['memorable_name']
            session['step1_data']['file'] = filename
            source_code = read_file_content(os.path.join(path_to_file, 'file_extraction_scripts', f'extract_pairs_from_{file_type}.py'))
            file_content = read_file_content(filename)
            return render_template('editor.j2', source_code=source_code, file_content=file_content, file_type=file_type, memorable_name=memorable_name, filename=filename, help_text=help_text)
        
        if 'input_type' in request.form or session['step1_data']:
            session['step1_data'] = request.form
            if request.form['input_type'] == 'file':
                file_options = {
                    "JSON (.json)": "json",
                    "SimulEval output (.log)": "log",
                    "CSV (.csv)": "csv",
                    "TSV (.tsv)": "tsv",
                    "XML (.xml)": "xml",
                    "None of the above ": "txt",
                    }
                return render_template('file_input.j2', help_text=help_text, file_options=file_options) 
            else:
                return render_template('manual_input.j2', help_text=help_text)
    
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
        print(f"session in preview_pairs: {session}")
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
    
    @app.route('/visualize_instruct', methods=['POST','GET'])
    def visualize_instruct():
        """
        Visualize the instruct score.

        Returns:
            str: The rendered HTML template.
        """
        # Get page number from the request, default to 1 if not provided
        if 'ids' in request.form:
            ids = request.form.get('ids', '[]')
            files = tuple(json.loads(ids))
        
        elif 'files' in request.form:
            files = request.form.getlist('files')
            print(f"files fom next page: {files}, type: {type(files)}")
            # files = json.loads(files[0])
        else:
            files = request.form.getlist('selected_options')
        
        if isinstance(files, str):
            files = [files]
        
        search_options = []
        search_texts = []
        search_query = None
        conjunctions = []
        clear_search = False
        print(f'request.form in visualize_instruct: {request.form}')
        if 'search_options[]' and 'search_texts[]' in request.form:
            search_options = request.form.getlist('search_options[]')
            search_texts = request.form.getlist('search_texts[]')
            conjunctions = request.form.getlist('conjunctions[]')
            if len(search_options) > 0 and len(search_texts) > 0:
                search_query = construct_full_query(search_options, search_texts, conjunctions)
            print(f"search_option: {search_options}")
            print(f"search_text: {search_texts}")
            print(f"conjunctions: {conjunctions}")
        
        if 'search_query' in session and session['search_query'] and not search_query and not clear_search:
            search_query = session['search_query']
            search_options = session['search_options']
            search_texts = session['search_texts']
            conjunctions = session['conjunctions']
        session['search_query'] = search_query
        session['search_options'] = search_options
        session['search_texts'] = search_texts
        session['conjunctions'] = conjunctions
        
        print(f"session is {session}")
        input_data = []
        print(f"Selected files: {files}")
        
                    
        page_number = int(request.form.get('current_page', 1))
        print(f"Page number: {page_number}")
        
        load_items_per_page = ITEMS_PER_PAGE//len(files)
        load_items_per_page = load_items_per_page if load_items_per_page >= 1 else 1
        
        # Calculate the starting index based on the page number
        start_index = (page_number - 1) * load_items_per_page
        
        # get ids for files selected
        
        run_ids = tuple(files)
        
        # first get all references used in the selected files
        print(f"search_query: {search_query}")
        
        read_query = f"SELECT DISTINCT ref_id, refs.source_text FROM preds JOIN refs ON (refs.id = preds.ref_id) WHERE run_id IN {run_ids} ORDER BY ref_id OFFSET {start_index} LIMIT {load_items_per_page};"
        if search_query:
            read_query = f"SELECT DISTINCT ref_id, refs.source_text FROM preds JOIN refs ON (refs.id = preds.ref_id) WHERE run_id IN {run_ids} AND preds.id IN ({search_query}) ORDER BY ref_id OFFSET {start_index} LIMIT {load_items_per_page};"
            
        total_items_query = f"SELECT COUNT(DISTINCT ref_id) FROM preds WHERE run_id IN {run_ids};" 
        if search_query:
            total_items_query = f"SELECT COUNT(DISTINCT ref_id) FROM preds WHERE run_id IN {run_ids} AND preds.id IN ({search_query});"
        total_items = read_data(total_items_query, logging=logging)[0][0]
        print(total_items)
        
        results = read_data(read_query, logging=logging)
        ref_ids = tuple([result[0] for result in results])
        input_data = [{'reference': result[1], 'runs' : {}, 'ref_id': result[0]} for result in results]
        print(f"ref_ids: {ref_ids}")
        
        results = read_data(f"SELECT preds_text.source_text, error_type, error_scale, error_explanation, filename, ref_id, run_id, preds.id, preds.se_score  FROM preds JOIN preds_text ON (preds_text.pred_id = preds.id) JOIN runs ON (preds.run_id = runs.id) WHERE run_id IN {run_ids} AND ref_id IN {ref_ids} ORDER BY ref_id, preds.se_score DESC")
        
        empty_predictions_per_run = []
        for i in range(len(input_data)):
            for run_id in run_ids:
                # print(f'cur run_id: {run_id}, dict: {run_id_dict}')
                cur_filename = get_filename(run_id)
                input_data[i]['runs'][cur_filename] = {'prediction': {}}
                empty_predictions_per_run.append((i, cur_filename))
                popped = False
                for result in results:
                    if result[5] == input_data[i]['ref_id'] and cur_filename == result[4]:
                        input_data[i]['runs'][cur_filename]['prediction'][result[0]] =  {"error_type": result[1], "error_scale": result[2], "error_explanation": result[3]} if result[1] else "None"
                        if not popped:
                            empty_predictions_per_run.pop()
                            input_data[i]['runs'][cur_filename]['se_score'] = result[8]
                            input_data[i]['runs'][cur_filename]['pred_id'] = result[7]
                            popped = True
        print(f"empty_predictions_per_run: {empty_predictions_per_run}")
        for i, filename in empty_predictions_per_run:
            del input_data[i]['runs'][filename]
        # clean out the input_data to remove empty runs

        # SELECT DISTINCT ref_id, refs.source_text FROM preds JOIN refs ON (refs.id = preds.ref_id) WHERE run_id IN {run_ids} ORDER BY ref_id OFFSET {start_index} LIMIT {load_items_per_page}
        
        # SELECT SELECT preds_text.source_text, error_type, error_scale, error_explanation, filename  FROM preds JOIN preds_text ON (preds_text.pred_id = preds.id) JOIN runs ON (preds.run_id = runs.id) WHERE run_id IN (4,5,6) AND ref_id IN {ref_ids} ORDER BY ref_id, preds.se_score DESC
        # SORT BY run_id, se_score DESC
        
        # predictions = {result[0]: {"error_type": result[1], "error_scale": result[2], "error_explanation": result[3]} if result[1] else "None" for result in results}        #gluck figuring what this is lol
        # print(input_data)            
        json.dump(results, open('input_data.json', 'w'), indent=4)
        avg_errors = 1
        most_common_errors = {
            "error1": 3,
            "error2": 2,
            "error3": 1
        }
        num_errors = 1
        se_score = 0.5
        
        # Calculate total number of pages
        total_pages = (total_items + load_items_per_page - 1) // load_items_per_page
        help_text = help_text_json["visualize_instruct"]
        
        print(f"search_options: {search_options}")
        
            
        return render_template('visualize_instruct.j2', input_data=input_data, help_text=help_text, total_pages=total_pages, current_page=page_number, files=files, num_errors=num_errors, most_common_errors=most_common_errors, avg_errors=avg_errors, se_score=se_score,
                               search_options=search_options, search_texts=search_texts, conjunctions=conjunctions)
    
    def get_filename(run_id):
        if run_id not in run_id_dict:
            results = read_data(f"SELECT id, filename FROM runs WHERE id not in {tuple(run_id_dict.keys())}")
            for result in results:
                run_id_dict[result[0]] = result[1]
                
        return run_id_dict[int(run_id)]
    
    def construct_full_query(search_options, search_texts, conjunctions):
        search_query = "SELECT DISTINCT preds.id FROM preds"
        if 'preds_text.error_type' in search_options or 'preds_text.error_scale' in search_options or 'preds_text.error_explanation' in search_options:
            search_query += " JOIN preds_text ON (preds_text.pred_id = preds.id)"
        if 'runs.filename' in search_options:
            search_query += " JOIN runs ON (preds.run_id = runs.id)"
        if 'refs.source_text' in search_options or 'refs.lang' in search_options:
            search_query += " JOIN refs ON (refs.id = preds.ref_id)"
            
        
        is_last_conjunctor_not = False    
        for i, (search_option, search_text) in enumerate(zip(search_options, search_texts)):
            if i > 0:
                if conjunctions[i-1] == 'NOT':
                    search_query += f" AND preds.id NOT IN (SELECT preds.id FROM preds JOIN preds_text ON (preds_text.pred_id = preds.id) AND {search_option} LIKE '%{search_text}%')"
                    is_last_conjunctor_not = True
                else: 
                    search_query += f" {conjunctions[i-1]}"
            else:
                search_query += " WHERE"
            if not is_last_conjunctor_not:
                search_query += get_search_query(search_option, search_text)
            else:
                is_last_conjunctor_not = False
        return search_query
    
    def get_search_query(search_option, search_text):
        return f" {search_option} LIKE '%{search_text}%'"
    
    
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
            print(f"Error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 400
        
    def _delete_runs_subprocess(run_ids):
        for run_id in run_ids:
            kill_processes_by_run_id(run_id)
            print("Deleting run_id: ", run_id)
            write_data(f"DELETE FROM preds_text WHERE pred_id IN (SELECT id FROM preds WHERE run_id = {run_id}); DELETE FROM preds WHERE run_id = {run_id}; DELETE FROM runs WHERE id = {run_id}; DELETE FROM refs WHERE id NOT IN (SELECT ref_id FROM preds);")

    return app