import json
import os
path_to_file = os.path.dirname(os.path.abspath(__file__))


def extract_pairs_from_xml(file):
    """
    Extracts prediction-reference pairs from a xml file and creates a dictionairy containing those pairs

    Args:
        file (str): The path to the log file.

    Returns:
        pairs (list): A list of dictionaries, each containing a reference and a prediction.

    Raises:
        FileNotFoundError: If the specified log file does not exist.

    """
    pairs = []                # Holds the data that has been read in

    with open(file) as f:
        lines = f.readlines()   
        for line in lines:
            data = json.loads(line)     # Load the data from the line
            pairs.append({"prediction": data["prediction"], "reference": data["reference"]})
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