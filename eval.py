import torch
from datasets import load_dataset
from tqdm import tqdm
import re
import argparse
import os
from collections import Counter
from dotenv import load_dotenv

import json
import sys

sys.setrecursionlimit(10000000)
print(sys.getrecursionlimit())

sys.path.append("/mnt/taurus/data1/chinmay")



KEY_INSTANCES = "instances"

parser = argparse.ArgumentParser()
parser.add_argument('--file_name', type=str, default=0)
parser.add_argument('--memorable_name', type=str, default=0)
args = parser.parse_args()

load_dotenv()

from InstructScore_SEScore3.InstructScore import InstructScore



def split_sentence_with_queries(sentence, queries):
    # Create a regular expression pattern to match any of the queries
    pattern = '|'.join(re.escape(query) for query in queries)
    # Split the sentence using the pattern as the delimiter
    parts = re.split(f'({pattern})', sentence, flags=re.IGNORECASE)

    # Filter out empty strings and None values
    phrases = [part.strip() for part in parts if part]

    return phrases


def get_score(text):
    keyword = re.escape('Major/minor: Major')
    num_major = re.findall(keyword, text, re.IGNORECASE)
    num_major = len(num_major)
    keyword = re.escape('Major/minor: Minor')
    num_minor = re.findall(keyword, text, re.IGNORECASE)
    num_minor = len(num_minor)
    # print(text)
    # print('-' * 50)
    # print(num_major, num_minor)
    # print('=' * 50)
    return max(-5 * num_major - num_minor, -25)

def process_text(text, prediction, error_type_counter):
    """
    Process the given text and extract error information.

    Args:
        text (str): The input text to process.
        prediction (str): The predicted text.
        error_type_counter (dict): A dictionary to keep track of error types and their counts.

    Returns:
        tuple: A tuple containing the following:
            - pred_render_data (dict): A dictionary mapping phrases to error information.
            - num_errors (int): The number of errors found in the text.
            - error_type_counter (dict): The updated error type counter.

    """
    # print(text)
    se_score = 0
    text = text + '\n'
    num_pattern = r'Your Translation contains (\d+) errors:'
    num_errors = re.search(num_pattern, text)
    if num_errors is None:
        num_errors = 0
    else:
        num_errors = int(num_errors.group(1))
    
    pred_render_data = {}
    if num_errors == 0:
        pred_render_data[prediction] = "None"
        return pred_render_data, 0, error_type_counter, 0
    # Define regular expression patterns
    error_pattern = r'Error type (\d+): (.+?)\nMajor/minor: (.+?)\nError location (\d+): (.+?)\nExplanation for error \d+: (.+?)\n'

    # Use re.findall() to find all matches of the patterns in the text
    matches = re.findall(error_pattern, text)
    # print(f"Matches found: {matches}")
    # print(f"text: {text}")
    
    queries = []
    query_dict = []

    # Create a dictionary to store error information
   
    for match in matches:
        error_num = int(match[0])
        error_type = match[1]
        error_scale = match[2]
        error_location = match[4][1:-1]
        error_explanation = match[5]
        
        error_type_counter[error_type] += 1

        queries.append(error_location)
        query_dict.append({
            'error_type': error_type,
            'error_scale': error_scale,
            'error_location': error_location,
            'error_explanation': error_explanation
        })
        if error_scale == "Major":
            se_score -= 5
        else:
            se_score -= 1
        
    phrases = split_sentence_with_queries(prediction, queries)
    for phrase in phrases:
        query_match = False
        for i,query in enumerate(queries):
            if query.lower() in phrase.lower():
                query_match = True
                pred_render_data[phrase] = query_dict[i]
                break
        if not query_match:
            pred_render_data[phrase] = "None"
    
        
    return pred_render_data, num_errors, error_type_counter, se_score


model_path = 'xu1998hz/InstructScore'

file_name = args.file_name
memorable_name = args.memorable_name
if file_name == 0:
    raise ValueError("File name not provided")
else:
    print(file_name)

batch_size = 1
extensions = "json"
data = load_dataset(
    extensions,
    data_files=[file_name],
    field=KEY_INSTANCES,
    split="train",
    use_auth_token=None,
    cache_dir=os.environ["HF_ASSETS_CACHE"]
)
# print(f"This is data: {data}")

# naive partition on training and validation set, 10,000 vs 500
eval_dataset=data

# model_path = 'xu1998hz/InstructScore'
# model = LlamaForCausalLM.from_pretrained(model_path, torch_dtype=torch.bfloat16, cache_dir=os.environ["HF_HOME"]).to('cuda')
# tokenizer = LlamaTokenizer.from_pretrained(model_path, cache_dir=os.environ["HF_HOME"])
# tokenizer.pad_token = tokenizer.eos_token

gt_scores, pred_scores = [], []

output_json = []


task_type = "mt_en-es"
scorer = InstructScore(task_type=task_type, batch_size=batch_size, cache_dir='/mnt/gemini/data1/chinmay/transformers_cache')

total_errors = 0
error_type_counter = Counter()
se_score_total = 0
for i in tqdm(range(0, len(eval_dataset), batch_size)):
    eval_reference = [eval_dataset[j]['reference'] for j in range(i, min(i + batch_size, len(eval_dataset)))]
    eval_prediction = [eval_dataset[j]['prediction'] for j in range(i, min(i + batch_size, len(eval_dataset)))]
    if None in eval_reference:
        print(f"None in eval_batch")
        print(i)
    # if i == 0:
    #     print(eval_reference)
    #     print(eval_prediction)
    batch_outputs, scores_ls = scorer.score(ref_ls=eval_reference, out_ls=eval_prediction)
    for j in range(len(batch_outputs)):
        if j < 3: 
            print(batch_outputs[j])
        prediction = eval_dataset[i+j]['prediction']
        pred_render_dict, num_errors, error_type_counter, se_score = process_text(batch_outputs[j], prediction, error_type_counter)
        total_errors += num_errors
        se_score_total += se_score
        reference = eval_dataset[i+j]['reference']
        output_json.append({
            'prediction': pred_render_dict,
            'reference': reference,
        })
    if i < 100:
        output_json.append({
            'stats': {
                'num_errors': total_errors,
                'most_common_errors': error_type_counter.most_common(3),
                'average_num_errors': total_errors/len(output_json),
                'se_score': se_score_total/len(output_json)
            }
        })
        # print("overwriting last dump")
        json.dump(output_json, open(f"{os.path.dirname(os.path.abspath(__file__))}/jobs/{memorable_name}/{memorable_name}_instructscore.json", "w"), indent=2)
        output_json.pop(-1)

output_json.append({
            'stats': {
                'num_errors': total_errors,
                'most_common_errors': error_type_counter.most_common(None),
                'average_num_errors': total_errors/((i+1)*batch_size),
                'se_score': se_score_total/((i+1)*batch_size)
            }
        })

json.dump(output_json, open(f"{os.path.dirname(os.path.abspath(__file__))}/jobs/{memorable_name}/{memorable_name}_instructscore.json", "w"), indent=2)
     



