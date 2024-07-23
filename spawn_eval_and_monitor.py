import os
import argparse
from readwrite_database import write_data, read_data
import subprocess
import time
import sys

path_to_file = os.path.dirname(os.path.abspath(__file__))

def spawn_eval(run_name, src_lang, tgt_lang):
    # Define the command to run
    job_path = os.path.join(path_to_file, "jobs", run_name)   
    # with open(os.path.join(job_path, f"{run_name}_out.txt"), "w") as out_file:
    #     out_file.write("spawning eval!")
    write_data(f"INSERT INTO runs (filename, source_lang, target_lang, in_progress, run_type) VALUES ('{run_name}', '{src_lang}', '{tgt_lang}', 0, 'instruct');")
    run_id = read_data("SELECT id FROM runs ORDER BY id DESC LIMIT 1")[0][0]
    
    command = f"{sys.executable} {os.path.join(path_to_file, "eval.py")} --run_id {run_id} --run_name {run_name} --src_lang {src_lang} --tgt_lang {tgt_lang}"
    # Execute the command
    process = subprocess.run(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Retrieve the process ID
    status = process.returncode
    # Update the database with the process ID
    write_data(f"UPDATE runs SET exit_status = {status} WHERE id = '{run_id}'")
    if status == 0:
        os.remove(os.path.join(job_path, f"{run_name}_err.txt"))
        os.remove(os.path.join(job_path, f"{run_name}_out.txt"))
        os.remove(os.path.join(job_path, f"{run_name}_extracted.json"))
        os.rmdir(job_path)
    else:
        write_data(f"UPDATE runs SET path_to_err = '{os.path.join(job_path, f"{run_name}_err.txt")}' WHERE id = '{run_id}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--run_name', type=str, required=True)
    parser.add_argument('--src_lang', type=str, required=True)
    parser.add_argument('--tgt_lang', type=str, required=True)
    args = parser.parse_args()

    spawn_eval(args.run_name, args.src_lang, args.tgt_lang)