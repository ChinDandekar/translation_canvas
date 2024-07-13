import duckdb
import os
import fasteners
from datetime import datetime

path_to_db = os.path.join(os.path.dirname(__file__), 'temporary.db') 
path_to_rwlock = os.path.join(os.path.dirname(__file__), 'tmp', 'duckdb.lock')
if not os.path.exists(path_to_rwlock):
    open(path_to_rwlock, 'w').close()
now = datetime.now()
    
rw_lock = fasteners.InterProcessReaderWriterLock(path_to_rwlock)
log_file = open(os.path.join(os.path.dirname(__file__), 'tmp', 'log.txt'), 'a')

def write_data(query: str, logging = False) -> list:
    if logging:
        pid = os.getpid()
    with rw_lock.write_lock():
        if logging:
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            log_file.write(f"{dt_string}: writing data lock acquired by {pid}\n")
        conn = duckdb.connect(path_to_db)
        results = conn.execute(query).fetchall()
        conn.close()
        # db_lock.release_write()
    if logging:
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        log_file.write(f"{dt_string}: writing data lock released by {pid}\n")
        log_file.flush()
    return results

def read_data(query: str, logging=False) -> list:
    if logging:
        pid = os.getpid()
    with rw_lock.read_lock():
        if logging:
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            log_file.write(f"{dt_string}: reading data lock acquired by {pid}\n")
        conn = duckdb.connect(path_to_db, read_only=True)
        result = conn.execute(query).fetchall()
        conn.close()
    if logging:
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        log_file.write(f"{dt_string}: reading data lock released by {pid}\n")
        log_file.flush()
    return result
