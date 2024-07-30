import json
import os
path_to_file = os.path.dirname(os.path.abspath(__file__))

# Please don't change the function signature
def extract_pairs_from_log(files: list[str]) -> list:
    """
    Extracts prediction-reference pairs from a SimulEval log file and creates a dictionairy containing those pairs

    Args:
        files (list[str]): A list of file paths to the inputted log files.

    Returns:
        pairs (list): A list of dictionaries, each containing a reference and a prediction.

    Raises:
        FileNotFoundError: If the specified log file does not exist.

    """
    pairs = []                # Holds the data that has been read in

    with open(files) as f:
        lines = f.readlines()   
        for line in lines:
            data = json.loads(line)     # Load the data from the line
            pairs.append({"prediction": data["prediction"], "reference": data["reference"]})
            # Add only prediction and reference data to the pairs list
    # Please don't change return value
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