
import os
import subprocess
import sys
import json
from translation_canvas.utils import read_file_content, write_file_content, spawn_independent_process, _delete_runs_subprocess
from translation_canvas.readwrite_database import read_data, read_data_df
from translation_canvas.setup import setup_system

from flask import Flask, render_template, request, session, jsonify, send_from_directory, redirect, url_for
import secrets
import rocher.flask
from werkzeug.utils import secure_filename

import plotly, plotly.express as px
import plotly.graph_objs as go
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
        help_text = help_text_json["index"]
        if not os.path.exists(os.path.join(path_to_file, ".env")) or not os.path.exists(os.path.join(path_to_file, "translation_canvas.db")):
            return render_template('setup.j2',  title='Translation Canvas', help_text=help_text)
        
        
        # clean out session
        session.clear()
        runs = read_data("SELECT id, filename, source_lang, target_lang, in_progress, se_score, bleu_score, num_predictions, run_type, exit_status FROM runs ORDER BY target_lang, se_score, bleu_score DESC;", logging=logging)
        print(runs)
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
        print(f"session in process_input_form: {session}")
        print(f"process_input_form request.form: {request.form}")
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
        print(f"command: {command}")      
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
        print(f"available_gpus: {available_gpus}")
        
        return render_template('input_form.j2', help_text=help_text, source_languages=source_languages, 
                               target_languages=target_languages, 
                               language_names=language_names, available_gpus=available_gpus)
    
    @app.route('/input_form/step2', methods=['GET', 'POST'])
    def file_input():
        """
        Render the file_input.j2 template.

        Returns:
            str: The rendered HTML template.
        """
        help_text = help_text_json["file_input"]
        
        if 'gpus' in request.form:
            json.dump(request.form.getlist('gpus'), open(CUDA_DEVICES_FILE, 'w'), indent=4)
        

        
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
        
        if 'input_method' in request.form or session['step1_data']:
            session['step1_data'] = request.form.to_dict()
            evaluation_type = session['step1_data']['evaluation_type'] if 'step1_data' in session and 'evaluation_type' in session['step1_data'] else None
            if 'evaluation_type' in request.form:
                evaluation_type = request.form.getlist('evaluation_type')
            session['step1_data']['evaluation_type'] = evaluation_type
            print(f"current session in file_input right after input_form: {session}")
            
            data_types = session['step1_data']['data_types'] if 'step1_data' in session and 'data_types' in session['step1_data'] else None
            if 'data_types' in request.form:
                data_types = request.form['data_types']
                
            src = False if data_types == 'ref' else True
            ref = False if data_types == 'src' else True
            print(f"src: {src}, ref: {ref}")
                
                
            if request.form['input_method'] == 'file':
                file_options = {
                    "JSON (.json)": "json",
                    "SimulEval output (.log)": "log",
                    "CSV (.csv)": "csv",
                    "TSV (.tsv)": "tsv",
                    "XML (.xml)": "xml",
                    "Text (.txt) ": "txt",
                    }
                return render_template('file_input.j2', help_text=help_text, file_options=file_options) 
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
            
            query = f"""
                WITH RankedErrors AS (
                    SELECT preds.run_id, 
                        error_type, 
                        COUNT(*) AS Count,
                        ROW_NUMBER() OVER (PARTITION BY preds.run_id ORDER BY COUNT(*) DESC) AS row_num
                    FROM preds_text
                    JOIN preds ON preds_text.pred_id = preds.id
                    WHERE error_type IS NOT NULL
                    AND preds.run_id IN {stats_dict['instruct']}
                    GROUP BY preds.run_id, error_type
                )
                SELECT run_id, error_type AS 'Error Type', Count
                FROM RankedErrors
                WHERE row_num <= 10
                ORDER BY Count, run_id DESC;
                """
            error_type_df = read_data_df(query, logging=logging)
            error_type_df['Run'] = error_type_df['run_id'].apply(get_filename)  # Add the run filename directly to the DataFrame

            query = construct_distribution_query('se_score', 'InstructScore', stats_dict['instruct'], precision=0)
            instructscore_distribution_df = read_data_df(query, logging=logging)
            instructscore_distribution_df['Run'] = instructscore_distribution_df['run_id'].apply(get_filename)
            
            error_type_graph = create_histogram(error_type_df, xaxis_title='Error Type', yaxis_title='Count', title='InstructScore: Frequency of types of errors')
            instructscore_distribution_graph = create_histogram(instructscore_distribution_df, xaxis_title='InstructScore', yaxis_title='Count', title='InstructScore: Distribution of scores per instance')
                
                
        comet_distribution_graph = None
        if comet:
            stats_dict['comet'] = tuple(stats_dict['comet'])
            categories.append('COMET')
            
            query = construct_distribution_query('comet_score', 'CometScore', stats_dict['comet'])
            comet_distribution_df = read_data_df(query, logging=logging)
            comet_distribution_df['Run'] = comet_distribution_df['run_id'].apply(get_filename)
            # Calculate the bar width
            comet_distribution_graph = create_histogram(comet_distribution_df, xaxis_title='CometScore', yaxis_title='Count', title='COMET: Distribution of scores per instance', bar_width=None)
                
        if bleu:
            categories.append('BLEU')
            

        query = f"""
                SELECT id AS run_id, 
                    COALESCE(se_score, NULL, 0) AS InstructScore, 
                    COALESCE(bleu_score, NULL, 0) AS BLEU, 
                    COALESCE(comet_score, NULL, 0) AS COMET 
                    FROM runs 
                    WHERE id IN {ids};"""
        scores_df = read_data_df(query, logging=logging)
        # Normalize columns between 0.25 and 0.9
        
        ranges = {
            "InstructScore": [-20, -6], # InstructScore
            "BLEU": [0, 45], # BLEU
            "COMET": [0, 0.8] # COMET
        }
        normalized_df = pd.DataFrame()
        for i, category in enumerate(categories):
            normalized_df[category] = scores_df[category].apply(lambda x: (x - ranges[category][0]) / (ranges[category][1] - ranges[category][0]))
        normalized_df['run_id'] = scores_df['run_id']
        scores_radar_chart = create_radar_chart(scores_df, normalized_df, categories)
        
        session['compare_systems_ids'] = ids
       
        return render_template('dashboard.j2', help_text=help_text, instructscore=instructscore, bleu=bleu, comet=comet, error_type_graph=error_type_graph, instructscore_distribution_graph=instructscore_distribution_graph, comet_distribution_graph=comet_distribution_graph, scores_radar_chart=scores_radar_chart)

    
    def create_radar_chart(df, normalized_df, categories):

        # Define colors for the radar chart
        
        contrast_colors = ['rgba(63, 81, 181, 0.3)', 'rgba(233, 30, 99, 0.3)', 'rgba(255, 152, 0, 0.3)', 'rgba(76, 175, 80, 0.3)', 'rgba(0, 188, 212, 0.3)', 'rgba(156, 39, 176, 0.3)', 'rgba(255, 235, 59, 0.3)']

        # Create radar chart
        fig = go.Figure()
        
        # Add traces for each run_id
        for index, row in normalized_df.iterrows():
            text = [f'{category}: {round(df[category][index], 2)}' for category in categories]
            text.append(f'{categories[0]}: {round(df[categories[0]][index], 2)}')  # close the loop
            fig.add_trace(go.Scatterpolar(
                r=[row[category] for category in categories] + [row[categories[0]]],  # close the loop
                theta=categories + [categories[0]],  # close the loop
                fill='toself',
                fillcolor=contrast_colors[index % len(contrast_colors)],
                line_color=contrast_colors[index % len(contrast_colors)],
                name=f'{get_filename(row["run_id"])}',
                text=text,
                textposition='top center',
                marker=dict(size=10)  # Adjust marker size here
            ))

        # Customize layout
        fig.update_layout(
            polar=dict(
                bgcolor='white',
                radialaxis=dict(
                    visible=False,
                    range=[0, 1]
                ),
                angularaxis=dict(
                    tickvals=[i for i in range(len(categories))],  # Add ticks for the categories
                    ticktext=categories,
                    linecolor='black',
                    linewidth=2
                )
            ),
            showlegend=True,
            plot_bgcolor='white',  # Set the plot background to white
            paper_bgcolor='white',  # Set the paper background to white
            title="Scores: "+', '.join([category for category in categories]),
            title_font=dict(color='black', size=24),
            legend_title_text='Runs'
        )

        radar_chart = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return radar_chart
    
    def create_histogram(df, xaxis_title, yaxis_title, title, bar_width=None):
        # Create the bar chart using Plotly
        fig = px.bar(
            df,
            x=xaxis_title,
            y=yaxis_title,
            color='Run',
            barmode='group',
            title=title,
            labels={'Category': 'Category', 'Count': 'Count'}
        )
        

        
        # Update the layout with specified colors
        fig.update_layout(
            plot_bgcolor='white',
            font=dict(color='black'),
            title_font=dict(color='black', size=24),
            xaxis=dict(
                showgrid=False, 
                linecolor='black', 
                ticks='',  # Hide tick marks
                tickvals = [],  # Hide tick marks
                ticktext=[],  # Hide tick text
                automargin=True
            ),
            yaxis=dict(
                showgrid=False, 
                gridcolor='#f4f4f9', 
                linecolor='black', 
                ticks='outside',
                automargin=True
            ),
            legend_title_text='Runs',
        )
        if bar_width:
            fig.update_traces(width=bar_width)

        
        # Convert the plot to JSON
        histogram = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return histogram
    
    def construct_distribution_query(score, score_name, ids, bins=10.0, precision=2):
        return f"""
            WITH MinMax AS (
                SELECT 
                    run_id,
                    MIN({score}) AS min_score,
                    MAX({score}) AS max_score
                FROM preds 
                WHERE preds.run_id IN {ids}
                GROUP BY run_id
            ),
            BinInfo AS (
                SELECT 
                    run_id,
                    min_score,
                    max_score,
                    (max_score - min_score) / {bins} AS bin_size
                FROM MinMax
            ),
            BinnedScores AS (
                SELECT 
                    preds.run_id,
                    {score},
                    min_score,
                    bin_size,
                    FLOOR(({score} - min_score) / bin_size) AS bin_index
                FROM preds
                JOIN BinInfo ON preds.run_id = BinInfo.run_id
                WHERE preds.run_id IN {ids}
            ),
            RangeCounts AS (
                SELECT 
                    run_id,
                    bin_index,
                    MIN(min_score + bin_index * bin_size) AS range_start,
                    MAX(min_score + (bin_index + 1) * bin_size - 1) AS range_end,
                    COUNT(*) AS count
                FROM BinnedScores
                GROUP BY run_id, bin_index
            )
            SELECT 
                run_id,
                ROUND((range_start + range_end) / 2, {precision}) AS {score_name},
                count AS Count
            FROM RangeCounts
            ORDER BY run_id, range_start;
        """
    
    @app.route('/visualize_instruct', methods=['POST','GET'])
    def visualize_instruct():
        """
        Visualize the instruct score.

        Returns:
            str: The rendered HTML template.
        """
        # Get page number from the request, default to 1 if not provided
        print(f'request.form in visualize_instruct: {request.form}')
        if 'ids' in request.form:
            ids = request.form.get('ids', '[]')
            files = tuple(json.loads(ids))
        
        elif 'files' in request.form:
            files = request.form.getlist('files')
            print(f"files fom next page: {files}, type: {type(files)}")
            # files = json.loads(files[0])
        
        elif 'compare_systems_ids' in session:
            files = session['compare_systems_ids']
            print(f"files from session: {files}")
        
        else:
            files = request.form.getlist('selected_options')
        
        if isinstance(files, str):
            files = [files]
        
        search_options = []
        search_texts = []
        search_query = None
        conjunctions = []
        if 'search_options[]' and 'search_texts[]' in request.form:
            search_options = request.form.getlist('search_options[]')
            search_texts = request.form.getlist('search_texts[]')
            search_texts = [text.replace("'", "''") for text in search_texts]
            conjunctions = request.form.getlist('conjunctions[]')
            if len(search_options) > 0 and len(search_texts) > 0:
                search_query = construct_full_query(search_options, search_texts, conjunctions)
            print(f"search_option: {search_options}")
            print(f"search_text: {search_texts}")
            print(f"conjunctions: {conjunctions}")
        
        if 'search_query' in session and session['search_query'] and not search_query:
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
        
        
        read_query = (
            f"""SELECT DISTINCT ref_id,
                src_id,    
                s.source_text,
                r.source_text
                FROM 
                    preds p
                LEFT JOIN 
                    src s ON p.src_id = s.id
                LEFT JOIN 
                    refs r ON p.ref_id = r.id
                WHERE 
                    run_id IN {run_ids} 
               """
                            )
        if search_query:
            read_query += f"AND p.id IN ({search_query}) "
        
        read_query += f"""
             ORDER BY
                    ref_id, src_id
                OFFSET 
                        {start_index} 
                LIMIT 
                    {load_items_per_page};
            """
        total_items_query = (
                              f"SELECT COUNT( * ) FROM (SELECT DISTINCT ref_id, src_id FROM preds WHERE run_id IN {run_ids})  "
                            )
        if search_query:
            total_items_query = f"SELECT COUNT( * ) FROM (SELECT DISTINCT ref_id, src_id FROM preds WHERE run_id IN {run_ids} AND preds.id IN ({search_query}));"
        print(search_query)
        total_items = read_data(total_items_query, logging=logging)[0][0]
        print(total_items)
        
        results = read_data(read_query, logging=logging)
        ref_ids = tuple([result[0] for result in results])
        src_ids = tuple([result[1] for result in results])
        
        ref_ids_sql = f"({','.join([str(ref_id) for ref_id in ref_ids if ref_id])})"
        src_ids_sql = f"({','.join([str(src_id) for src_id in src_ids if src_id])})"
        input_data = {(result[0], result[1]): {'reference': result[3], 'runs' : {}, "source": result[2]} for result in results}       # use ref_id and src_id as a unique id for each instance
        print(f"ref_ids: {ref_ids}")
        print(f"src_ids: {src_ids}")
        print(f"run_ids: {run_ids}")
        read_query = (
                f"""SELECT preds_text.source_text, 
                            preds_text.error_type, 
                            preds_text.error_scale, 
                            preds_text.error_explanation, 
                            runs.filename, 
                            preds.ref_id, 
                            preds.id, 
                            preds.se_score, 
                            preds.comet_score,
                            preds.src_id,
                            preds_text.id
                            FROM preds 
                            JOIN preds_text 
                            ON (preds_text.pred_id = preds.id) 
                            JOIN runs
                            ON (runs.id = preds.run_id)
                            WHERE run_id IN {run_ids} 
                            """
                )
        
        if len(ref_ids_sql) > 2 and len(src_ids_sql) > 2:
            read_query += f"AND (preds.ref_id IN {ref_ids_sql} OR preds.src_id IN {src_ids_sql}) "
        elif len(ref_ids_sql) > 2:
            read_query += f"AND preds.ref_id IN {ref_ids_sql} "
        elif len(src_ids_sql) > 2:
            read_query += f"AND preds.src_id IN {src_ids_sql} "
        else:
            read_query += "AND 1=0 "
        read_query += f"ORDER BY preds.ref_id, preds.src_id;"
        print(f"read_query: {read_query}")
        results = read_data(read_query, logging=logging)
        
        does_search_have_error = False
        if len(results) > 0:
            for option in search_options:
                if 'error' in option and not does_search_have_error:
                    pred_ids = tuple([result[6] for result in results])
                    preds_text_seach_query = construct_pred_text_query(search_options, search_texts, conjunctions, pred_ids)
                    print(f"this is preds_text_seach_query: {preds_text_seach_query}")
                    preds_text_search_results = read_data(preds_text_seach_query, logging=logging)
                    print(f"preds_text_search_results: {preds_text_search_results}")
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
        
        print(f"search_options: {search_options}")
        
            
        return render_template('visualize_instruct.j2', input_data=input_data, help_text=help_text, total_pages=total_pages, current_page=page_number, files=files, search_options=search_options, search_texts=search_texts, conjunctions=conjunctions)
    
    def get_filename(run_id):
        if run_id not in run_id_dict:
            if len(run_id_dict) == 0:
                results = read_data(f"SELECT id, filename FROM runs;")
            else:
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
            search_query += " LEFT JOIN refs ON (refs.id = preds.ref_id)"
        if 'src.source_text' in search_options or 'src.lang' in search_options:
            search_query += " LEFT JOIN src ON (src.id = preds.src_id)"
            
        
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
    
    def construct_pred_text_query(search_options, search_texts, conjunctions, pred_ids):
        search_option_errors, search_query_errors, conjunction_errors = trim_search_query_for_error(search_options, search_texts, conjunctions)
        
        search_query = "SELECT DISTINCT preds_text.id FROM preds_text"
        is_last_conjunctor_not = False    
        for i, (search_option, search_text) in enumerate(zip(search_option_errors, search_query_errors)):
            if i > 0:
                if conjunction_errors[i-1] == 'NOT':
                    search_query += f" AND preds_text.id NOT IN (SELECT preds_text.id FROM preds_text WHERE {search_option} LIKE '%{search_text}%')"
                    is_last_conjunctor_not = True
                else: 
                    search_query += f" {conjunction_errors[i-1]}"
            else:
                search_query += " WHERE"
            if not is_last_conjunctor_not:
                search_query += get_search_query(search_option, search_text)
            else:
                is_last_conjunctor_not = False
        
        search_query += f" AND preds_text.pred_id IN {pred_ids};"
        return search_query
        
    def trim_search_query_for_error(search_option, search_query, conjunctions):
        search_option_errors = []
        search_query_errors = []
        conjunction_errors = []
        for i, option in enumerate(search_option):
            if 'error' in option:
                search_option_errors.append(option)
                search_query_errors.append(search_query[i])
                conjunction_errors.append(conjunctions[i] if i < len(conjunctions) else 'AND')
        return search_option_errors, search_query_errors, conjunction_errors
    
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
    
    @app.route('/clear_search_cache', methods=['POST'])
    def clear_search_cache():
        print(f"session before clearing: {session}")
        if 'search_options' in session:
            del session['search_options']
        if 'search_texts' in session:
            del session['search_texts']
        if 'search_query' in session:
            del session['search_query']
        if 'conjunctions' in session:
            del session['conjunctions']
        print(f"session after clearing: {session}")
        return jsonify({"status": "success", "message": "Search cache cleared"}), 200


    return app