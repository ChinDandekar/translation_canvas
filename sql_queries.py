from translation_canvas.readwrite_database import read_data

run_id_dict = {}

def error_type_distribution_query(stats_dict):
    query = f"""
            WITH RankedErrors AS (
                SELECT preds.run_id, 
                    error_type, 
                    COUNT(*) AS Count,
                    ROW_NUMBER() OVER (PARTITION BY preds.run_id ORDER BY COUNT(*) DESC) AS row_num
                FROM preds_text
                JOIN preds ON preds_text.pred_id = preds.id
                WHERE error_type IS NOT NULL
                AND preds.run_id IN {stats_dict['instruct']}
                GROUP BY preds.run_id, error_type
            )
            SELECT run_id, error_type AS 'Error Type', Count
            FROM RankedErrors
            WHERE row_num <= 10
            ORDER BY Count, run_id DESC;
            """
        
    return query   

def get_scores(ids):
    query = f"""
            SELECT id AS run_id, 
                COALESCE(se_score, NULL, 0) AS InstructScore, 
                COALESCE(bleu_score, NULL, 0) AS BLEU, 
                COALESCE(comet_score, NULL, 0) AS COMET 
                FROM runs 
                WHERE id IN {ids};"""
                
    return query

def get_filename(run_id):
        if run_id not in run_id_dict:
            if len(run_id_dict) == 0:
                results = read_data(f"SELECT id, filename FROM runs;")
            else:
                results = read_data(f"SELECT id, filename FROM runs WHERE id not in {tuple(run_id_dict.keys())}")
            for result in results:
                run_id_dict[result[0]] = result[1]
                
        return run_id_dict[int(run_id)]

def construct_distribution_query(score, score_name, ids, bins=10.0, precision=2):
        return f"""
            WITH MinMax AS (
                SELECT 
                    run_id,
                    MIN({score}) AS min_score,
                    MAX({score}) AS max_score
                FROM preds 
                WHERE preds.run_id IN {ids}
                GROUP BY run_id
            ),
            BinInfo AS (
                SELECT 
                    run_id,
                    min_score,
                    max_score,
                    (max_score - min_score) / {bins} AS bin_size
                FROM MinMax
            ),
            BinnedScores AS (
                SELECT 
                    preds.run_id,
                    {score},
                    min_score,
                    bin_size,
                    FLOOR(({score} - min_score) / bin_size) AS bin_index
                FROM preds
                JOIN BinInfo ON preds.run_id = BinInfo.run_id
                WHERE preds.run_id IN {ids}
            ),
            RangeCounts AS (
                SELECT 
                    run_id,
                    bin_index,
                    MIN(min_score + bin_index * bin_size) AS range_start,
                    MAX(min_score + (bin_index + 1) * bin_size - 1) AS range_end,
                    COUNT(*) AS count
                FROM BinnedScores
                GROUP BY run_id, bin_index
            )
            SELECT 
                run_id,
                ROUND((range_start + range_end) / 2, {precision}) AS {score_name},
                count AS Count
            FROM RangeCounts
            ORDER BY run_id, range_start;
        """
    
def construct_full_search_query(search_options, search_texts, conjunctions):
    search_query = "SELECT DISTINCT preds.id FROM preds"
    if 'preds_text.error_type' in search_options or 'preds_text.error_scale' in search_options or 'preds_text.error_explanation' in search_options:
        search_query += " JOIN preds_text ON (preds_text.pred_id = preds.id)"
    if 'runs.filename' in search_options:
        search_query += " JOIN runs ON (preds.run_id = runs.id)"
    if 'refs.source_text' in search_options or 'refs.lang' in search_options:
        search_query += " LEFT JOIN refs ON (refs.id = preds.ref_id)"
    if 'src.source_text' in search_options or 'src.lang' in search_options:
        search_query += " LEFT JOIN src ON (src.id = preds.src_id)"
        
    
    is_last_conjunctor_not = False    
    for i, (search_option, search_text) in enumerate(zip(search_options, search_texts)):
        if i > 0:
            if conjunctions[i-1] == 'NOT':
                search_query += f" AND preds.id NOT IN (SELECT preds.id FROM preds JOIN preds_text ON (preds_text.pred_id = preds.id) AND {search_option} LIKE '%{search_text}%')"
                is_last_conjunctor_not = True
            else: 
                search_query += f" {conjunctions[i-1]}"
        else:
            search_query += " WHERE"
        if not is_last_conjunctor_not:
            search_query += get_search_query(search_option, search_text)
        else:
            is_last_conjunctor_not = False
    return search_query

def construct_pred_text_query(search_options, search_texts, conjunctions, pred_ids):
    search_option_errors, search_query_errors, conjunction_errors = trim_search_query_for_error(search_options, search_texts, conjunctions)
    
    search_query = "SELECT DISTINCT preds_text.id FROM preds_text"
    is_last_conjunctor_not = False    
    for i, (search_option, search_text) in enumerate(zip(search_option_errors, search_query_errors)):
        if i > 0:
            if conjunction_errors[i-1] == 'NOT':
                search_query += f" AND preds_text.id NOT IN (SELECT preds_text.id FROM preds_text WHERE {search_option} LIKE '%{search_text}%')"
                is_last_conjunctor_not = True
            else: 
                search_query += f" {conjunction_errors[i-1]}"
        else:
            search_query += " WHERE"
        if not is_last_conjunctor_not:
            search_query += get_search_query(search_option, search_text)
        else:
            is_last_conjunctor_not = False
    
    search_query += f" AND preds_text.pred_id IN {pred_ids};"
    return search_query
    
def trim_search_query_for_error(search_option, search_query, conjunctions):
    search_option_errors = []
    search_query_errors = []
    conjunction_errors = []
    for i, option in enumerate(search_option):
        if 'error' in option:
            search_option_errors.append(option)
            search_query_errors.append(search_query[i])
            conjunction_errors.append(conjunctions[i] if i < len(conjunctions) else 'AND')
    return search_option_errors, search_query_errors, conjunction_errors

def get_search_query(search_option, search_text):
    return f" {search_option} LIKE '%{search_text}%'"

def get_all_refs_query(search_query, load_items_per_page, start_index, run_ids):
    read_query = (
        f"""SELECT DISTINCT ref_id,
            src_id,    
            s.source_text,
            r.source_text
            FROM 
                preds p
            LEFT JOIN 
                src s ON p.src_id = s.id
            LEFT JOIN 
                refs r ON p.ref_id = r.id
            WHERE 
                run_id IN {run_ids} 
            """
                        )
    if search_query:
        read_query += f"AND p.id IN ({search_query}) "
    
    read_query += f"""
            ORDER BY
                ref_id, src_id
            OFFSET 
                    {start_index} 
            LIMIT 
                {load_items_per_page};
        """
        
    return read_query

def get_instances_query(run_ids, ref_ids_sql, src_ids_sql):
    read_query = (
            f"""SELECT preds_text.source_text, 
                        preds_text.error_type, 
                        preds_text.error_scale, 
                        preds_text.error_explanation, 
                        runs.filename, 
                        preds.ref_id, 
                        preds.id, 
                        preds.se_score, 
                        preds.comet_score,
                        preds.src_id,
                        preds_text.id
                        FROM preds 
                        JOIN preds_text 
                        ON (preds_text.pred_id = preds.id) 
                        JOIN runs
                        ON (runs.id = preds.run_id)
                        WHERE run_id IN {run_ids} 
                        """
            )
    
    if len(ref_ids_sql) > 2 and len(src_ids_sql) > 2:
        read_query += f"AND (preds.ref_id IN {ref_ids_sql} OR preds.src_id IN {src_ids_sql}) "
    elif len(ref_ids_sql) > 2:
        read_query += f"AND preds.ref_id IN {ref_ids_sql} "
    elif len(src_ids_sql) > 2:
        read_query += f"AND preds.src_id IN {src_ids_sql} "
    else:
        read_query += "AND 1=0 "
    read_query += f"ORDER BY preds.ref_id, preds.src_id;"
    return read_query