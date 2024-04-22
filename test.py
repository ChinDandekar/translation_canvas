import re
import subprocess
import json
import gpustat
from collections import Counter


def split_sentence_with_queries(sentence, queries):
    # Create a regular expression pattern to match any of the queries
    pattern = '|'.join(re.escape(query) for query in queries)
    # Split the sentence using the pattern as the delimiter
    parts = re.split(f'({pattern})', sentence, flags=re.IGNORECASE)

    # Filter out empty strings and None values
    phrases = [part.strip() for part in parts if part]

    return phrases

# sentence = "Necesito que subas, que pases el fuego, y necesito que le consigas un par de zapatos. (Risas) Como si fuera un lugar."
# queries = ["test seNtence", "to be", "many"]

# result = split_sentence_with_queries(sentence, queries)
# print(result)


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







# free_gpu_indices = get_free_gpus()
# print(free_gpu_indices)

def test_counter():
    test_counter = Counter()
    test_counter['test'] += 1
    print(test_counter.most_common(1))

def test_overwrite():
    some_json = {
        "test": "test",
        "test2": "test2"
    }
    json.dump(some_json, open("test.json", "w"), indent=2)
    some_json = {
        "test": "test3",
        "test2": "test4"
    }
    json.dump(some_json, open("test.json", "w"), indent=2)
test_overwrite()