import os
import argparse
from translation_canvas.readwrite_database import write_data, read_data
import subprocess
import time
import sys

path_to_file = os.path.dirname(os.path.abspath(__file__))

def spawn_eval(run_name, src_lang, tgt_lang, instructscore, bleu, comet, ref, src):
    # Define the command to run
    job_path = os.path.join(path_to_file, "jobs", run_name)   
    
    run_type = ""
    command = f"{sys.executable} {os.path.join(path_to_file, "eval.py")} --run_name {run_name} --src_lang {src_lang} --tgt_lang {tgt_lang}"
    if instructscore:
        run_type += 'i'
        command += " --instructscore True"
    if bleu:
        run_type += 'b'
        command += " --bleu True"
    if comet:
        run_type += 'c'
        command += " --comet True"
        
    if ref:
        command += " --ref True"
    if src:
        command += " --src True"
    
    write_data(f"INSERT INTO runs (filename, source_lang, target_lang, in_progress, run_type) VALUES ('{run_name}', '{src_lang}', '{tgt_lang}', 0, '{run_type}');")
    run_id = read_data("SELECT id FROM runs ORDER BY id DESC LIMIT 1")[0][0]
    command += f" --run_id {run_id}"
    
    
    # Execute the command
    print(f"executing command: {command}")
    process = subprocess.run(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    # Print the stderr from the subprocess
    if process.stderr:
        print(f"stderr: {process.stderr.decode()}")
    # Retrieve the process ID
    status = process.returncode
    print(f"Process {run_name} finished with status {status}")
    # Update the database with the process ID
    write_data(f"UPDATE runs SET exit_status = {status} WHERE id = '{run_id}'")
    # if status == 0:
    #     os.remove(os.path.join(job_path, f"{run_name}_err.txt"))
    #     os.remove(os.path.join(job_path, f"{run_name}_out.txt"))
    #     os.remove(os.path.join(job_path, f"{run_name}_extracted.json"))
    #     os.rmdir(job_path)
    # else:
    #     write_data(f"UPDATE runs SET path_to_err = '{os.path.join(job_path, f"{run_name}_err.txt")}' WHERE id = '{run_id}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--run_name', type=str, required=True)
    parser.add_argument('--src_lang', type=str, required=True)
    parser.add_argument('--tgt_lang', type=str, required=True)
    parser.add_argument('--instructscore', type=bool, default=False)
    parser.add_argument('--bleu', type=bool, default=False)
    parser.add_argument('--comet', type=bool, default=False)
    parser.add_argument('--ref', type=bool, default=False)
    parser.add_argument('--src', type=bool, default=False)
    args = parser.parse_args()
    
    print(f"Spawning evaluation for {args.run_name} with src_lang={args.src_lang}, tgt_lang={args.tgt_lang}, instructscore={args.instructscore}, bleu={args.bleu}, comet={args.comet} and ref={args.ref}, src={args.src}")

    spawn_eval(args.run_name, args.src_lang, args.tgt_lang, args.instructscore, args.bleu, args.comet, args.ref, args.src)