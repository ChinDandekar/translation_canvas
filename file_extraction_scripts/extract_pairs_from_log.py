import json
import os
path_to_file = os.path.dirname(os.path.abspath(__file__))

# Please don't change the function signature
def extract_pairs_from_log(file: str) -> list:
    """
    Extracts prediction-reference pairs from a SimulEval log file and creates a dictionairy containing those pairs

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
    # Please don't change return value
    raise TypeError("whoops here's an error")
    return pairs