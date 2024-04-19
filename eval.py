import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from tqdm import tqdm
import re
import argparse
import os

import json


KEY_INSTANCES = "instances"

parser = argparse.ArgumentParser()
parser.add_argument('--file_name', type=str, default=0)
parser.add_argument('--memorable_name', type=str, default=0)
args = parser.parse_args()

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

def process_text(text, prediction):
    # print(text)
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
        return pred_render_data
    # Define regular expression patterns
    error_pattern = r'Error type (\d+): (.+?)\nMajor/minor: (.+?)\nError location (\d+): (.+?)\nExplanation for error \d+: (.+?)\n'

    # Use re.findall() to find all matches of the patterns in the text
    matches = re.findall(error_pattern, text)
    print(f"Matches found: {matches}")
    print(f"text: {text}")
    
    queries = []
    query_dict = []

    # Create a dictionary to store error information
   
    for match in matches:
        error_num = int(match[0])
        error_type = match[1]
        error_scale = match[2]
        error_location = match[4][1:-1]
        error_explanation = match[5]

        queries.append(error_location)
        query_dict.append({
            'error_type': error_type,
            'error_scale': error_scale,
            'error_location': error_location,
            'error_explanation': error_explanation
        })
        
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
    
        
    return pred_render_data


model_path = '/mnt/taurus/home/guangleizhu/instructscore_spanish/new_ft/checkpoint-565'

file_name = args.file_name
memorable_name = args.memorable_name
if file_name == 0:
    raise ValueError("File name not provided")
else:
    print(file_name)

batch_size = 20
extensions = "json"
data = load_dataset(
    extensions,
    data_files=[file_name],
    field=KEY_INSTANCES,
    split="train",
    use_auth_token=None,
)
print(f"This is data: {data}")

# naive partition on training and validation set, 10,000 vs 500
eval_dataset=data


model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.bfloat16).to('cuda')
tokenizer = AutoTokenizer.from_pretrained(model_path)
tokenizer.pad_token = tokenizer.eos_token

gt_scores, pred_scores = [], []

output_json = []




# run inference on the eval_dataset
for i in tqdm(range(0, len(eval_dataset), batch_size)):
    eval_batch = [eval_dataset[j]['input'] for j in range(i, min(i + batch_size, len(eval_dataset)))]
    if None in eval_batch:
        print(f"None in eval_batch")
        print(type(eval_batch))
        print(i)
    eval_batch = tokenizer(eval_batch, return_tensors="pt", padding=True, truncation=True, max_length=1024)
    eval_batch = eval_batch.to('cuda')
    with torch.no_grad():
        outputs = model.generate(**eval_batch, max_new_tokens=512, num_return_sequences=1, do_sample=True, pad_token_id=tokenizer.eos_token_id)
        
        for j in range(len(outputs)):
            text = tokenizer.decode(outputs[j], skip_special_tokens=True)
            prediction = eval_dataset[i+j]['prediction']
            pred_render_dict = process_text(text, prediction)
            reference = eval_dataset[i+j]['reference']
            output_json.append({
                'prediction': pred_render_dict,
                'reference': reference,
            })



print(output_json)
json.dump(output_json, open(f"{os.path.dirname(os.path.abspath(__file__))}/jobs/{memorable_name}/{memorable_name}_instructscore.json", "w"), indent=2)
