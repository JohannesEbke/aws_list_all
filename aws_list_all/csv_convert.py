from pandas.io.json import json_normalize


def convert_file(json_file, operation):
    try:
        normalized = json_normalize(json_file)
        normalized.to_csv(operation)
    except AttributeError as err:
        print("### Cannot create a .csv file due to nature of the json file (" + str(err) + ")")
