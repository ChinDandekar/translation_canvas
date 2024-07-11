import json
import os
path_to_file = os.path.dirname(os.path.abspath(__file__))


def extract_pairs_from_json(file):
    """
    Converts a SimulEval log file to a JSON file with specific formatting.

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

    if not os.path.exists(f"{path_to_file}/jobs/{memorable_name}"):
        os.mkdir(f"{path_to_file}/jobs/{memorable_name}")
    json.dump(ansJson, open(f"{path_to_file}/jobs/{memorable_name}/{new_file}.json", "w"), indent=2)
    return new_file