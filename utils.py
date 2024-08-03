import os
import re
import subprocess
import psutil
from translation_canvas.readwrite_database import write_data

path_to_file = os.path.dirname(os.path.abspath(__file__))


def _delete_runs_subprocess(run_ids):
    for run_id in run_ids:
        kill_processes_by_run_id(run_id)
        print("Deleting run_id: ", run_id)
        write_data(f"DELETE FROM preds_text WHERE pred_id IN (SELECT id FROM preds WHERE run_id = {run_id}); DELETE FROM preds WHERE run_id = {run_id}; DELETE FROM runs WHERE id = {run_id}; DELETE FROM refs WHERE id NOT IN (SELECT ref_id FROM preds);")
    
def spawn_independent_process(command):
    
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True, universal_newlines=True)
    return process.pid
    
def split_sentence_with_queries(sentence, queries):
    """
    Split a sentence into phrases using a list of queries as delimiters.

    Args:
        sentence (str): The sentence to be split.
        queries (list): A list of queries to be used as delimiters.

    Returns:
        list: A list of phrases obtained by splitting the sentence using the queries as delimiters.
    """
    # Create a regular expression pattern to match any of the queries
    pattern = '|'.join(re.escape(query) for query in queries)
    # Split the sentence using the pattern as the delimiter
    parts = re.split(f'({pattern})', sentence, flags=re.IGNORECASE)

    # Filter out empty strings and None values
    phrases = [part.strip() for part in parts if part]

    return phrases

def read_file_content(file_path):
    with open(file_path, 'r') as file:
        return file.read(1000000)
    
def write_file_content(file_path, content):
    with open(file_path, 'w') as file:
        return file.write(content)
    
def kill_processes_by_run_id(selected_run_id):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        # print(f"Checking process {proc.info['pid']}")
        try:
            cmdline = proc.info['cmdline']
            if cmdline:
                # Convert the command line to a single string
                cmdline_str = ' '.join(cmdline)
                # Check if the command line contains the selected run_id
                if f'eval.py --run_id {selected_run_id}' in cmdline_str:
                    print(f"Killing process {proc.info['pid']} with command: {cmdline_str}")
                    proc.terminate()  # or proc.kill() if you want to force kill
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            print(f"Error while trying to kill process {proc.info['pid']}, error: {e}")
            pass