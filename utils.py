import json
import os
import string
import re
import subprocess

path_to_file = os.path.dirname(os.path.abspath(__file__))


def get_completed_jobs():
    """
    Get the list of completed jobs.

    Returns:
        list: A list of completed jobs.
    """
    jobs = os.listdir(os.path.join(path_to_file, "jobs"))
    
def get_free_gpus():
    command = ['gpustat', '--json']
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        gpu_info = json.loads(result.stdout)
    else:
        raise RuntimeError("Failed to get GPU information")
    
    free_indices = []
    for gpu in gpu_info['gpus']:
        if gpu['memory.used'] <= 100:
            free_indices.append(gpu['index'])
    return free_indices

def create_and_exec_slurm(memorable_name, file_name):
    """
    Creates and executes a SLURM job script for running a Python script with specified parameters.

    Args:
        memorable_name (str): A unique name for the job.
        file_name (str): The name of the input file.
        email (str): The email address to receive notifications about the job.

    Returns:
        int: The exit status of the job execution.
    """
    free_gpus = get_free_gpus()
    with open(f"{file_name}.sh", "w") as f:
        f.write("#!/usr/bin/env bash\n\n\n" + 
                "#SBATCH --nodes=1\n" +
                "#SBATCH --ntasks=1\n" + 
                "#SBATCH --cpus-per-task=32\n" +
                "#SBATCH --mem=128GB\n" +
                "#SBATCH --gpus=1\n" + 
                "#SBATCH --partition=aries\n" + 
                "#SBATCH --time=5-2:34:56\n" +
                "#SBATCH --account=chinmay\n" +
                "#SBATCH --mail-type=ALL\n" +
                f"#SBATCH --mail-user=cdandekar@ucsb.edu\n" +
                f"#SBATCH --output={file_name}_slurm_out.txt\n" + 
                f"#SBATCH --error={file_name}_slurm_err.txt")
        
        f.write("\n\n")
        visible_devices = ",".join([str(i) for i in free_gpus[:2]])
        f.write(f"export CUDA_VISIBLE_DEVICES={visible_devices}\n")
        f.write(f"cd {path_to_file}/..\n")
        f.write(f'python {path_to_file}/eval.py --file_name "{file_name}" --memorable_name {memorable_name}')
    pid = os.fork()
    if pid==0:
        os.chdir(f"{path_to_file}/jobs/{memorable_name}")
        os.system(f"sbatch {file_name}.sh")
        os._exit(0)
    else:
        os.waitpid(pid, 0)
        return 0
    
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

def instructscore_to_dict(memorable_name, start_index, items_per_page):
    """
    Converts the contents of an instructscore JSON file into a dictionary and performs pagination.

    Args:
        memorable_name (str): The name of the instructscore file.
        start_index (int): The starting index for pagination.
        items_per_page (int): The number of items per page for pagination.

    Returns:
        tuple: A tuple containing the following elements:
            - render_data (list): The subset of data based on pagination.
            - total_length (int): The total length of the data.
            - num_errors (int): The number of errors in the data.
            - most_common_errors (list): The most common errors in the data.
            - avg_errors (float): The average number of errors per data item.
    """
    file_path = f"{path_to_file}/jobs/{memorable_name}/{memorable_name}_instructscore.json"
    
    with open(file_path) as f:
        data = json.load(f)
        
        # Calculate the end index based on start index and items per page
        end_index = start_index + items_per_page
        
        # Retrieve the subset of data based on pagination
        if end_index > len(data)-1:
            end_index = len(data)-1
        
        total_length = len(data)
        print(total_length)
        render_data = data[start_index:end_index]
        
        stats = data[-1]["stats"]
        num_errors = stats["num_errors"]
        most_common_errors = stats["most_common_errors"]
        se_score = stats["se_score"]
        avg_errors = num_errors/total_length       
        
    return render_data, total_length, num_errors, most_common_errors, avg_errors, se_score

def read_file_content(file_path):
    with open(file_path, 'r') as file:
        return file.read()
    
def write_file_content(file_path, content):
    with open(file_path, 'w') as file:
        return file.write(content)