import duckdb
import os
import click

@click.command()
def setup_system():
    path_to_file = os.path.dirname(__file__)
    if not os.path.exists(os.path.join(path_to_file, "tmp")):
        os.makedirs(os.path.join(path_to_file, "tmp"))

    lock_file_path = os.path.join(path_to_file, "tmp", "duckdb.lock")
    if not os.path.exists(lock_file_path):
        open(lock_file_path, 'w').close()
        
    job_path = os.path.join(path_to_file, "jobs")
    if not os.path.exists(job_path):
        os.makedirs(job_path)
        
    uploaded_files_path = os.path.join(path_to_file, "uploaded_files")
    if not os.path.exists(uploaded_files_path):
        os.makedirs(uploaded_files_path)

    database_path = os.path.join(path_to_file, 'translation_canvas.db')
    con = duckdb.connect(database=database_path)

    results = con.execute("CREATE SEQUENCE runs_id_sequence START 1;")
    results = con.execute("CREATE SEQUENCE refs_id_sequence START 1;")
    results = con.execute("CREATE SEQUENCE src_id_sequence START 1;")
    results = con.execute("CREATE SEQUENCE preds_id_sequence START 1;")
    results = con.execute("CREATE SEQUENCE preds_text_id_sequence START 1;")

    results = con.execute("""
                        CREATE TABLE IF NOT EXISTS runs (
                            id INT PRIMARY KEY DEFAULT nextval('runs_id_sequence'), 
                            filename VARCHAR(255) NOT NULL, 
                            source_lang VARCHAR(2) NOT NULL,   
                            target_lang VARCHAR(2) NOT NULL,
                            in_progress FLOAT,
                            exit_status INT,
                            path_to_err VARCHAR(255),
                            se_score FLOAT,
                            bleu_score FLOAT,
                            comet_score FLOAT,
                            num_predictions INT,
                            run_type VARCHAR(10));""")

    results = con.execute("""CREATE TABLE IF NOT EXISTS refs (
                                id INT DEFAULT nextval('refs_id_sequence') PRIMARY KEY, 
                                source_text TEXT NOT NULL, 
                                lang VARCHAR(2));""")
    
    results = con.execute("""CREATE TABLE IF NOT EXISTS src (
                                id INT DEFAULT nextval('src_id_sequence') PRIMARY KEY, 
                                source_text TEXT NOT NULL, 
                                lang VARCHAR(2));""")

    results = con.execute("""
                        CREATE TABLE IF NOT EXISTS preds (
                            id INT DEFAULT nextval('preds_id_sequence') PRIMARY KEY,
                            source_text TEXT,
                            se_score FLOAT,
                            comet_score FLOAT,
                            num_errors INT,
                            src_id INT,
                            ref_id INT,
                            run_id INT,
                            FOREIGN KEY (src_id) REFERENCES src(id),
                            FOREIGN KEY (ref_id) REFERENCES refs(id),
                            FOREIGN KEY (run_id) REFERENCES runs(id));""")

    results = con.execute("""
                    CREATE TABLE IF NOT EXISTS preds_text (
                        id INT DEFAULT nextval('preds_text_id_sequence') PRIMARY KEY,
                            source_text TEXT NOT NULL,
                            error_type VARCHAR(255),
                            error_scale VARCHAR (8),
                            error_location TEXT,
                            error_explanation TEXT,
                            pred_id INT,
                            FOREIGN KEY (pred_id) REFERENCES preds(id));""")   

    con.close()
    