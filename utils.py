import json
import os
import string
import re
import subprocess


def convert_log_to_json(file, src_lang, tgt_lang, memorable_name):
    """
    Converts a log file to a JSON file with specific formatting.

    Args:
        file (str): The path to the log file.
        src_lang (str): The source language for the translation task.
        tgt_lang (str): The target language for the translation task.
        memorable_name (str): A memorable name for the job.

    Returns:
        str: The name of the newly created JSON file.

    Raises:
        FileNotFoundError: If the specified log file does not exist.

    """
    new_file = file.split("/")[-2]
    outputs = []

    with open(file) as f:
        lines = f.readlines()
        for i,line in enumerate(lines):
            data = json.loads(line)
            outputs.append([data["prediction"], data["reference"]])
    
    ansJson = {"type": "text2text"}
    all_outputs = []
    for output in outputs:
        inputString = f"You are evaluating {src_lang}-to-{tgt_lang} Machine translation task. The correct translation is \"{output[1]}\". The model generated translation is \"{output[0]}\". Please identify all errors within each model output, up to a maximum of five. For each error, please give me the corresponding error type, major/minor label, error location of the model generated translation and explanation for the error. Major errors can confuse or mislead the reader due to significant change in meaning, while minor errors don't lead to loss of meaning but will be noticed."
        all_outputs.append({"input": inputString, "reference": output[1], "prediction": output[0]})

    ansJson["instances"] = all_outputs
    if not os.path.exists(f"{os.path.dirname(os.path.abspath(__file__))}/jobs/{memorable_name}"):
        os.mkdir(f"{os.path.dirname(os.path.abspath(__file__))}/jobs/{memorable_name}")
    json.dump(ansJson, open(f"{os.path.dirname(os.path.abspath(__file__))}/jobs/{memorable_name}/{new_file}.json", "w"), indent=2)
    return new_file
    
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

def create_and_exec_slurm(memorable_name, file_name, email):
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
    with open(f"{os.path.dirname(os.path.abspath(__file__))}/jobs/{memorable_name}/{memorable_name}_{file_name}.sh", "w") as f:
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
                f"#SBATCH --mail-user={email}\n" +
                f"#SBATCH --output=/mnt/taurus/data1/chinmay/instructscore_visualizer/jobs/{memorable_name}/{memorable_name}_{file_name}_slurm_out.txt\n" + 
                f"#SBATCH --error=/mnt/taurus/data1/chinmay/instructscore_visualizer/jobs/{memorable_name}/{memorable_name}_{file_name}_slurm_err.txt")
        
        f.write("\n\n")
        visible_devices = ",".join([str(i) for i in free_gpus])
        f.write(f"export CUDA_VISIBLE_DEVICES={visible_devices}\n")
        f.write(f'python {os.path.dirname(os.path.abspath(__file__))}/eval.py --file_name "/mnt/taurus/data1/chinmay/instructscore_visualizer/jobs/{memorable_name}/{file_name}.json" --memorable_name {memorable_name}')
    pid = os.fork()
    if pid==0:
        os.chdir(f"{os.path.dirname(os.path.abspath(__file__))}/jobs/{memorable_name}")
        os.system(f"sbatch {os.path.dirname(os.path.abspath(__file__))}/jobs/{memorable_name}/{memorable_name}_{file_name}.sh")
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
    file_path = f"{os.path.dirname(os.path.abspath(__file__))}/jobs/{memorable_name}/{memorable_name}_instructscore.json"
    
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
        avg_errors = num_errors/total_length       
        
    return render_data, total_length, num_errors, most_common_errors, avg_errors