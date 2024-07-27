import json
import os
path_to_file = os.path.dirname(os.path.abspath(__file__))


def extract_pairs_from_csv(files: list[str]) -> list:
    """
    Extracts source-prediction-reference tuples (if available) from a .csv file and creates a dictionairy containing those pairs
   
    Args:
        files (list[str]): A list of file paths to the inputted csv files.

    Returns:
        pairs (list): A list of dictionaries, each containing a reference and a prediction.

    Raises:
        FileNotFoundError: If the specified log file does not exist.

    """
    pairs = []                # Holds the data that has been read in

    with open(files[0]) as f:
        lines = f.readlines()   
        for line in lines:
            data = json.loads(line)     # Load the data from the line
            pairs.append({"prediction": data["prediction"], "reference": data["reference"]})
            # Add only prediction and reference data to the pairs list
    return pairs


"""
After running this script, if it ran correctly, the output should look like (assuming source and reference 
included in the csv file):
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