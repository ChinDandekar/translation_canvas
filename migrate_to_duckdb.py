import duckdb
import os
import json

path_to_db = 'visualizer.db'
con = duckdb.connect(database=path_to_db)
path_to_jobs = 'jobs/'

jobs = os.listdir(path_to_jobs)
for job in jobs:
    if os.path.exists(os.path.join(path_to_jobs, job, f'{job}_instructscore.json')):
        with open(os.path.join(path_to_jobs, job, f'{job}_instructscore.json')) as f:
            data = json.load(f)
            filename = job
            source_lang = 'en'
            target_lang = 'es'
            in_progress = 1
            exit_status = 0
            path_to_err = None
            se_score = -12
            num_predictions = 12820
            run_type = 'instruct'
            results = con.execute(f"INSERT INTO runs (filename, source_lang, target_lang, in_progress, exit_status, se_score, num_predictions, run_type) VALUES ('{filename}', '{source_lang}', '{target_lang}', {in_progress}, {exit_status}, {se_score}, {num_predictions}, '{run_type}');")
            
            run_id = con.execute(f"SELECT id FROM runs ORDER BY id DESC LIMIT 1").fetchall()[0][0]
            with open(os.path.join(path_to_jobs, job, f'{job}_instructscore.json')) as f:
                data = json.load(f)
                for pair in data:
                    if 'reference' in pair:
                        source_text = pair['reference']
                        source_text = source_text.replace("'", "''")
                        ref_id = con.execute(f"SELECT id FROM refs WHERE source_text = '{source_text}';").fetchall()
                        if ref_id == []:
                            results = con.execute(f"INSERT INTO refs (source_text, lang) VALUES ('{source_text}', 'es');")
                            ref_id = con.execute(f"SELECT id FROM refs ORDER BY id DESC LIMIT 1").fetchall()
                        ref_id = ref_id[0][0]
                        
                        prediction = pair['prediction']
                        num_errors = len([pred for pred in prediction if 'error_type' in prediction[pred]])
                        results = con.execute(f"INSERT INTO preds (se_score, num_errors, ref_id, run_id) VALUES ({se_score}, {num_errors}, {ref_id}, {run_id});")
                        pred_id = con.execute(f"SELECT id FROM preds ORDER BY id DESC LIMIT 1").fetchall()[0][0]
                        
                        for pred in prediction:
                            se_score = -12
                            pred_source_text = pred.replace("'", "''")
                            if 'error_type' in prediction[pred]:
                                error_type = prediction[pred]['error_type'].replace("'", "''")
                                error_scale = prediction[pred]['error_scale']
                                error_explanation = prediction[pred]['error_explanation'].replace("'", "''")
                                results = con.execute(f"INSERT INTO preds_text (source_text, error_type, error_scale, error_explanation, pred_id) VALUES ('{pred_source_text}', '{error_type}', '{error_scale}', '{error_explanation}', {pred_id});")
                            else:
                                results = con.execute(f"INSERT INTO preds_text (source_text, pred_id) VALUES ('{pred_source_text}', {pred_id});")
                                