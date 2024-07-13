from utils import spawn_independent_process
import os
import sys

path_to_file = os.path.dirname(os.path.abspath(__file__))
src = 'en'
tgt = 'es'
memorable_name = 'test_db'
command = f"{sys.executable} {os.path.join(path_to_file, 'spawn_eval_and_monitor.py')} --run_name {memorable_name} --src_lang {src} --tgt_lang {tgt}"
print(spawn_independent_process(command))