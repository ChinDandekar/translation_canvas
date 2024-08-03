from translation_canvas.file_extraction_scripts.extract_pairs_from_log import extract_pairs_from_log
from translation_canvas.file_extraction_scripts.extract_pairs_from_log import extract_pairs_from_log
from translation_canvas.file_extraction_scripts.extract_pairs_from_json import extract_pairs_from_json
from translation_canvas.file_extraction_scripts.extract_pairs_from_csv import extract_pairs_from_csv
from translation_canvas.file_extraction_scripts.extract_pairs_from_tsv import extract_pairs_from_tsv
from translation_canvas.file_extraction_scripts.extract_pairs_from_xml import extract_pairs_from_xml
from translation_canvas.file_extraction_scripts.extract_pairs_from_txt import extract_pairs_from_txt
from argparse import ArgumentParser
import os
import json

JOBS = os.path.join(os.path.dirname(__file__), 'jobs')
if not os.path.exists(JOBS):
    os.mkdir(JOBS)

parser = ArgumentParser()
parser.add_argument('--file_names', type=str, default="")
parser.add_argument('--memorable_name', type=str, default="")
parser.add_argument('--file_type', type=str, default="")

args = parser.parse_args()

if args.file_type == "log":
    pairs = extract_pairs_from_log(args.file_names)
elif args.file_type == "json":
    pairs = extract_pairs_from_json(args.file_names)
elif args.file_type == "csv":
    pairs = extract_pairs_from_csv(args.file_names)
elif args.file_type == "tsv":
    pairs = extract_pairs_from_tsv(args.file_names)
elif args.file_type == "xml":
    pairs = extract_pairs_from_xml(args.file_names)
else:
    pairs = extract_pairs_from_txt(args.file_names)
    
if not os.path.exists(os.path.join(JOBS, args.memorable_name)):
    os.mkdir(os.path.join(JOBS, args.memorable_name))
    
     
with open(os.path.join(JOBS, args.memorable_name, args.memorable_name + "_extracted.json"), 'w') as f:
    json.dump(pairs, f, indent=4)