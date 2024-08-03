import duckdb
import os
import fasteners
from datetime import datetime
import time
import random

path_to_db = os.path.join(os.path.dirname(__file__), 'translation_canvas.db') 
path_to_rwlock = os.path.join(os.path.dirname(__file__), 'tmp', 'duckdb.lock')
if not os.path.exists(path_to_rwlock):
    open(path_to_rwlock, 'w').close()
pid = os.getpid()



def write_data(query: str, logging = False) -> list:
    rw_lock = fasteners.InterProcessReaderWriterLock(path_to_rwlock)
    timer = 1
    success = False
    while not success:
        try:
            with rw_lock.write_lock():
                if logging:
                    log("writing data lock acquired")
                conn = duckdb.connect(path_to_db)
                results = conn.execute(query).fetchall()
                conn.commit()
                conn.close()
                success = True
            print("success")
        except duckdb.IOException:
            timer *= random.uniform(1, 2)           # exponential backoff
            print(f"backing off for {timer} seconds")
            time.sleep(timer)

    if logging:
        log("writing data lock released")
        
    return results

def read_data(query: str, logging=False) -> list:
    rw_lock = fasteners.InterProcessReaderWriterLock(path_to_rwlock)
    timer = 1
    success = False
    while not success:
        try:
            with rw_lock.read_lock():
                if logging:
                    log("reading data lock acquired")
                conn = duckdb.connect(path_to_db, read_only=True)
                result = conn.execute(query).fetchall()
                conn.close()
                success = True
        except duckdb.IOException:
            timer *= random.uniform(1, 2)       # exponential backoff
            print(f"backing off for {timer} seconds")
            time.sleep(timer)
        
    if logging:
        log("reading data lock released")
        
    return result

def read_data_df(query: str, logging=False) -> list:
    rw_lock = fasteners.InterProcessReaderWriterLock(path_to_rwlock)
    timer = 1
    success = False
    while not success:
        try:
            with rw_lock.read_lock():
                if logging:
                    log("reading data lock acquired for df")
                conn = duckdb.connect(path_to_db, read_only=True)
                result = conn.query(query).df()
                conn.close()
                success = True
        except duckdb.IOException:
            timer *= random.uniform(1, 2)       # exponential backoff
            print(f"backing off for {timer} seconds")
            time.sleep(timer)
        
    if logging:
        log("reading data lock released for df")
        
    return result

def log(message: str):
    with open(os.path.join(os.path.dirname(__file__), 'tmp', 'log.txt'), 'a') as log_file:
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        log_file.write(f"{dt_string}: {pid}: {message}\n")
        log_file.flush()
        os.fsync(log_file)