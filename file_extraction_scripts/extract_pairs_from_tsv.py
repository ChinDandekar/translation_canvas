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
    pairs = []                # Holds the data that has been read in

    translations = pd.read_csv(file, sep='\t')
    id_set = set()
    ref_set = set()
    for index, row in translations.iterrows():
        if row['globalSegId'] not in id_set and row['system'] == 'HW-TSC':
            pairs.append({'prediction': row['target'].replace("<v>", "").replace("</v>", "")})
            id_set.add(row['globalSegId'])
            # Add only prediction and reference data to the pairs list
        if row['globalSegId'] not in ref_set and row['system'] == 'refA':
            pairs[-1]['reference'] = row['target'].replace("<v>", "").replace("</v>", "")
            ref_set.add(row['globalSegId'])
    # raise Error
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