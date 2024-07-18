import duckdb
import os
import fasteners
from datetime import datetime

path_to_db = os.path.join(os.path.dirname(__file__), 'temporary.db') 
path_to_rwlock = os.path.join(os.path.dirname(__file__), 'tmp', 'duckdb.lock')
if not os.path.exists(path_to_rwlock):
    open(path_to_rwlock, 'w').close()
pid = os.getpid()



def write_data(query: str, logging = False) -> list:
    rw_lock = fasteners.InterProcessReaderWriterLock(path_to_rwlock)
    with rw_lock.write_lock():
        if logging:
            log("writing data lock acquired")
        conn = duckdb.connect(path_to_db)
        results = conn.execute(query).fetchall()
        conn.commit()
        conn.close()

    if logging:
        log("writing data lock released")
        
    return results

def read_data(query: str, logging=False) -> list:
    rw_lock = fasteners.InterProcessReaderWriterLock(path_to_rwlock)
    with rw_lock.read_lock():
        if logging:
            log("reading data lock acquired")
        conn = duckdb.connect(path_to_db, read_only=True)
        result = conn.execute(query).fetchall()
        conn.close()
        
    if logging:
        log("reading data lock released")
        
    return result

def log(message: str):
    with open(os.path.join(os.path.dirname(__file__), 'tmp', 'log.txt'), 'a') as log_file:
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        log_file.write(f"{dt_string}: {pid}: {message}\n")
        log_file.flush()
        os.fsync(log_file)