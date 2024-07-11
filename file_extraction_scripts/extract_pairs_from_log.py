import json
import os
path_to_file = os.path.dirname(os.path.abspath(__file__))

# Please don't change the function signature
def extract_pairs_from_log(file: str) -> list:
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
            # if 'Cuando' in data['prediction']:
            #     print("whoaaaaa")
            # Add only prediction and reference data to the pairs list
    print("oopsies")
    # raise TypeError("whoopsie daisy")
    return pairs