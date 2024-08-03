from tqdm import tqdm
import re
import argparse
import os
from collections import Counter
from dotenv import load_dotenv
from translation_canvas.readwrite_database import write_data, read_data
from InstructScore_SEScore3.InstructScore import InstructScore
from comet import download_model, load_from_checkpoint
import json
import sys
import sacrebleu


JOBS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs")
CUDA_PATH = os.path.join(os.path.dirname(JOBS_PATH), 'tmp', 'cuda_devices.json')

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
        return pred_render_data, 0, error_type_counter
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
    
    return pred_render_data, num_errors, error_type_counter

def setup_instructscore(src_lang, tgt_lang):
        
    batch_size = 20

    task_type = ""
    if src_lang=='zh':
        if tgt_lang=='en':
            task_type = 'mt_zh-en'
    elif src_lang=='en':
        if tgt_lang=='es':
            task_type = 'mt_en-es'
        elif tgt_lang=='ru':
            task_type = 'mt_en-ru'
        elif tgt_lang=='de':
            task_type = 'mt_en-de'

    scorer = InstructScore(task_type=task_type, batch_size=batch_size, cache_dir=os.environ['CACHE_DIR'])
    return scorer

def calculate_system_stats(dataset, ref, src, bleu, comet, run_id):
    if bleu:
        if ref:
            references = [dataset[j]['reference'] for j in range(0, len(dataset))]
            predictions = [dataset[j]['prediction'] for j in range(0, len(dataset))]
            bleu_score = sacrebleu.corpus_bleu(predictions, [references])
            write_data(f"UPDATE runs SET bleu_score = {bleu_score.score} WHERE id = {run_id};", logging=logging)
            print(f"Set BLEU score of {run_id} to {bleu_score.score}")
    
    if comet:
        if src and ref:
            model_path = download_model("Unbabel/wmt22-comet-da", saving_directory=os.environ['CACHE_DIR'])
            model = load_from_checkpoint(model_path)
            data = [{"src": dataset[j]['source'], "mt": dataset[j]['prediction'], "ref": dataset[j]['reference']} for j in range(0, len(dataset))]
            comet_score = model.predict(data)
            write_data(f"UPDATE runs SET comet_score = {comet_score['system_score']} WHERE id = {run_id};", logging=logging)
            print(f"Set COMET score of {run_id} to {comet_score['system_score']}")
            return comet_score['scores']
    return None

def evaluate(run_name, src_lang, tgt_lang, run_id, instructscore, bleu, is_comet, logging, ref, src):
    batch_size = 20
    eval_dataset=json.load(open(os.path.join(JOBS_PATH, run_name, f"{run_name}_extracted.json"), 'r'))
    
    if instructscore or is_comet:
        if os.path.exists(CUDA_PATH):
            cuda_devices = json.load(open(CUDA_PATH, 'r'))
            os.environ['CUDA_VISIBLE_DEVICES'] = ','.join(cuda_devices)
            print(f"Using GPUs: {','.join(cuda_devices)}")
        
    comet_scores = calculate_system_stats(eval_dataset, ref, src, bleu, is_comet, run_id)
    
    if instructscore:
        scorer = setup_instructscore(src_lang, tgt_lang)
        total_errors = 0
        error_type_counter = Counter()
    
    se_score_total = 0 if instructscore else 'NULL'
        
    for i in tqdm(range(0, len(eval_dataset), batch_size)):
        eval_prediction = [eval_dataset[j]['prediction'] for j in range(i, min(i + batch_size, len(eval_dataset)))]
        
        if instructscore:
            eval_reference = [eval_dataset[j]['reference'] for j in range(i, min(i + batch_size, len(eval_dataset)))]
            batch_outputs, scores_ls = scorer.score(ref_ls=eval_reference, out_ls=eval_prediction)
            
            
        for j in range(len(eval_prediction)):
            prediction = eval_dataset[i+j]['prediction'].replace("'", "''")
            
            if ref:
                reference = eval_dataset[i+j]['reference'].replace("'", "''")
                results = read_data(f"SELECT id FROM refs WHERE source_text = '{reference}';", logging=logging)
                if results == []:
                    results = write_data(f"INSERT INTO refs (source_text, lang) VALUES ('{reference}', '{tgt_lang}'); SELECT id FROM refs ORDER BY id DESC LIMIT 1;", logging=logging)
                ref_id = results[0][0]
            else: 
                ref_id = 'NULL'
            
            if src:
                source = eval_dataset[i+j]['source'].replace("'", "''")
                results = read_data(f"SELECT id FROM src WHERE source_text = '{source}';", logging=logging)
                if results == []:
                    results = write_data(f"INSERT INTO src (source_text, lang) VALUES ('{source}', '{src_lang}'); SELECT id FROM src ORDER BY id DESC LIMIT 1;", logging=logging)
                src_id = results[0][0]
            else:
                src_id = 'NULL'
            pred_render_dict = {prediction: "None"}
            se_score = scores_ls[j] if instructscore else 'NULL'
            comet_score = round(comet_scores[j],2) if comet_scores else 'NULL'
            num_errors = 'NULL'
            if instructscore:
                return_vals = process_text(batch_outputs[j], prediction, error_type_counter)
                pred_render_dict, num_errors, error_type_counter = return_vals
                total_errors += num_errors
                se_score_total += scores_ls[j]
            
            pred_id = write_data(f"INSERT INTO preds (se_score, comet_score, source_text, num_errors, src_id, ref_id, run_id) VALUES ({se_score}, {comet_score}, '{prediction}', {num_errors}, {src_id}, {ref_id}, {run_id}); SELECT id FROM preds ORDER BY id DESC LIMIT 1;", logging=logging)[0][0]
            
            for pred in pred_render_dict:
                pred_source_text = pred.replace("'", "''")
                if 'error_type' in pred_render_dict[pred]:
                    error_type = pred_render_dict[pred]['error_type'].replace("'", "''")
                    error_scale = pred_render_dict[pred]['error_scale']
                    error_explanation = pred_render_dict[pred]['error_explanation'].replace("'", "''")
                    results = write_data(f"INSERT INTO preds_text (source_text, error_type, error_scale, error_explanation, pred_id) VALUES ('{pred_source_text}', '{error_type}', '{error_scale}', '{error_explanation}', {pred_id});", logging=logging)
                else:
                    results = write_data(f"INSERT INTO preds_text (source_text, pred_id) VALUES ('{pred_source_text}', {pred_id});", logging=logging)
            
            
            total_evaluations = i + batch_size if i + batch_size < len(eval_dataset) else len(eval_dataset)
            final_se_score = se_score_total/total_evaluations if instructscore else 'NULL'
            results = write_data(f"UPDATE runs SET se_score = {final_se_score}, num_predictions = {total_evaluations}, in_progress = {total_evaluations/len(eval_dataset)} WHERE id = {run_id};", logging=logging)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--run_name', type=str, default=0)
    parser.add_argument('--src_lang', type=str, default=0)
    parser.add_argument('--tgt_lang', type=str, default=0)
    parser.add_argument('--run_id', type=int, default=0)
    parser.add_argument('--instructscore', type=bool, default=False)
    parser.add_argument('--bleu', type=bool, default=False)
    parser.add_argument('--comet', type=bool, default=False)
    parser.add_argument('--ref', type=bool, default=False)
    parser.add_argument('--src', type=bool, default=False)
    args = parser.parse_args()
    
    load_dotenv()
    
    logging = False
    
    run_name = args.run_name
    src_lang = args.src_lang
    tgt_lang = args.tgt_lang
    run_id = args.run_id
    instructscore = args.instructscore
    bleu = args.bleu
    is_comet = args.comet
    ref = args.ref
    src = args.src
    
    out_file = os.path.join(JOBS_PATH, run_name, f"{run_name}_out.txt")
    err_file = os.path.join(JOBS_PATH, run_name, f"{run_name}_err.txt")
    sys.stdout = open(out_file, 'w')
    sys.stderr = open(err_file, 'w')
    
    print(f"Running evaluation for {run_name} with src_lang={src_lang}, tgt_lang={tgt_lang}, run_id={run_id}, instructscore={args.instructscore}, bleu={args.bleu}, comet={args.comet}, ref={args.ref}, src={args.src}")

    evaluate(run_name, src_lang, tgt_lang, run_id, instructscore, bleu, is_comet, logging, ref, src)
    

        



