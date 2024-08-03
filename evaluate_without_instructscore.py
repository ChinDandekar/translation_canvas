from translation_canvas.readwrite_database import write_data, read_data
import json
import os
import argparse

path_to_file = os.path.dirname(os.path.abspath(__file__))
JOBS_PATH = os.path.join(path_to_file, "jobs")
logging = False

logging = False
def add_run_to_db(run_name, src_lang, tgt_lang):
    run_id = write_data(f"INSERT INTO runs (filename, source_lang, target_lang, in_progress, run_type) VALUES ('{run_name}', '{src_lang}', '{tgt_lang}', 0, 'none'); SELECT id FROM runs ORDER BY id DESC LIMIT 1")[0][0]
    pairs=json.load(open(os.path.join(JOBS_PATH, run_name, f"{run_name}_extracted.json"), 'r'))
    length = len(pairs)
    for i in range(length):
        reference = pairs[i]['reference'].replace("'", "''")
        prediction = pairs[i]['prediction'].replace("'", "''")
        results = read_data(f"SELECT id FROM refs WHERE source_text = '{reference}';", logging=logging)
        if results == []:
            results = write_data(f"INSERT INTO refs (source_text, lang) VALUES ('{reference}', '{tgt_lang}'); SELECT id FROM refs ORDER BY id DESC LIMIT 1;", logging=logging)
        ref_id = results[0][0]
        write_data(f"INSERT INTO preds (source_text, ref_id, run_id) VALUES ('{prediction}', {ref_id}, {run_id}); INSERT INTO preds_text (source_text, pred_id) VALUES ('{prediction}', (SELECT id FROM preds ORDER BY id DESC LIMIT 1));", logging=logging)[0][0]
        results = write_data(f"", logging=logging)
        if i % 100 == 0:
            write_data(f"UPDATE runs SET num_predictions = {i},in_progress = {i/length} WHERE id = {run_id};", logging=logging)
    results = write_data(f"UPDATE runs SET num_predictions = {length}, in_progress = 1, exit_status=0 WHERE id = {run_id};", logging=logging)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--run_name', type=str, required=True)
    parser.add_argument('--src_lang', type=str, required=True)
    parser.add_argument('--tgt_lang', type=str, required=True)
    args = parser.parse_args()

    add_run_to_db(args.run_name, args.src_lang, args.tgt_lang)