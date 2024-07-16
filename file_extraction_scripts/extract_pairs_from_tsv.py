import json
import os
import pandas as pd
path_to_file = os.path.dirname(os.path.abspath(__file__))


def extract_pairs_from_tsv(file):
    """
    Extracts prediction-reference pairs from a .tsv file and creates a dictionairy containing those pairs

    Args:
        file (str): The path to the log file.

    Returns:
        pairs (list): A list of dictionaries, each containing a reference and a prediction.

    Raises:
        FileNotFoundError: If the specified log file does not exist.

    """
    pairs = []
    translations = pd.read_csv(file, sep='\t')
    global_set = set()
    for index, row in translations.iterrows():
        if row['globalSegId'] not in global_set and row['system'] == 'ANVITA':
            global_set.add(row['globalSegId'])
            pairs.append({'prediction': row['target'], 'reference': row['source']})
    
            # Add only prediction and reference data to the pairs list
    
    return pairs

"""
This is what the expected output should look like:
[
    {
        prediction: "prediction1",
        reference: "reference1"
    },
    {
        prediction: "prediction2",
        reference: "reference2"
    },
    {
        prediction: "prediction3",
        reference: "reference3"
    },
    ...
]
"""