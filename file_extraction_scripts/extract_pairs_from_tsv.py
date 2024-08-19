import json
import os
import pandas as pd
path_to_file = os.path.dirname(os.path.abspath(__file__))


def extract_pairs_from_tsv(files: list[str]) -> list:
    """
    Extracts source-prediction-reference tuples (if available) from a .tsv file and creates a dictionairy containing those pairs

    Args:
        files (list[str]): A list of file paths to the inputted tsv files.

    Returns:
        pairs (list): A list of dictionaries, each containing a reference and a prediction.

    Raises:
        FileNotFoundError: If the specified files does not exist.

    """
    pairs = []                # Holds the data that has been read in

    print(files)
    translations = pd.read_csv(files, sep='\t')
    id_set = set()
    ref_set = set()
    src_set = set()
    for index, row in translations.iterrows():
        if row['globalSegId'] not in id_set and row['system'] == 'GPT4-5shot':
            pairs.append({'prediction': row['target'], 'source': row['source']})
            id_set.add(row['globalSegId'])
            # Add only prediction and reference data to the pairs list
        if row['globalSegId'] not in ref_set and row['system'] == 'refA':
            pairs[-1]['reference'] = row['target']
            ref_set.add(row['globalSegId'])
    # raise Error
    return pairs

"""
This is what the expected output should look like:
[
    {
        source: "source1",
        prediction: "prediction1",
        reference: "reference1"
    },
    {
        source: "source2",
        prediction: "prediction2",
        reference: "reference2"
    },
    {
        source: "source3",
        prediction: "prediction3",
        reference: "reference3"
    },
    ...
]
"""