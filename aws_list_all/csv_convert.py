import pandas.io.json
import sys


def convert_file(json_file, operation):
    try:
        normalized = pandas.io.json.json_normalize(json_file)
        normalized.to_csv(operation)
    except AttributeError as err:
        print("Cannot create a .csv file due to nature of the json file ({}) - File's name: {}. Retrying...".format(str(err), operation), file=sys.stderr)
        convert_file({
            "field1": json_file
        }, operation)
