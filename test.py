import re

def split_sentence_with_queries(sentence, queries):
    # Create a regular expression pattern to match any of the queries
    pattern = '|'.join(re.escape(query) for query in queries)
    # Split the sentence using the pattern as the delimiter
    parts = re.split(f'({pattern})', sentence, flags=re.IGNORECASE)

    # Filter out empty strings and None values
    phrases = [part.strip() for part in parts if part]

    return phrases

sentence = "Necesito que subas, que pases el fuego, y necesito que le consigas un par de zapatos. (Risas) Como si fuera un lugar."
queries = ["test seNtence", "to be", "many"]

result = split_sentence_with_queries(sentence, queries)
print(result)