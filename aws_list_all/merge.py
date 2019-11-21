import json
import glob
import os
from sys import stderr
from pyexcel.cookbook import merge_all_to_a_book
from aws_list_all import csv_convert, listing


def extract_identifier(data):
    false_identifier = {"ResponseMetadata",
                        "Owner"}
    for data_key in data:
        if data_key not in false_identifier:
            return data_key
    return ""


def merge_json_files(args):
    try:
        os.makedirs(args.output)
    except OSError:
        pass
    if args.session_name is not None:
        files_list = glob.glob("{}/*/{}/*.json".format(args.directory, args.session_name))
    else:
        files_list = glob.glob("{}/*/*.json".format(args.directory))
    if len(files_list) == 0:
        print("No file loaded, make sure you have entered correct parameters")
        exit(0)
    all_dic = dict()
    for file_path in files_list:
        service_name = file_path.split("/")[-1].replace(".json", "")
        region_idx = service_name.find("_")
        service_name = service_name[:region_idx]
        if args.verbose != 0:
            print("Adding service {} from '{}'".format(service_name, file_path))
        with open(file_path) as file:
            full_content = json.load(file)
            identifier = extract_identifier(full_content["response"])
            if identifier != "":
                file_content = full_content["response"][extract_identifier(full_content["response"])]
            else:
                file_content = full_content["response"]
            try:
                if service_name in all_dic:
                    if args.verbose > 1:
                        print("=> Service {} (from '{}') is already in the summary, adding the additional content...".format(service_name, file_path))
                    all_dic.update(
                        {service_name: all_dic[service_name] + file_content})
                else:
                    all_dic.update({service_name: file_content})
            except TypeError:
                print("Passing service {} (from '{}') because of a TypeError and cannot be added to the all resources...".format(service_name, file_path), file=stderr)
    for service in all_dic:
        try:
            all_dic[service] = [i for n, i in enumerate(all_dic[service]) if
                                i not in all_dic[service][n + 1:]]
        except TypeError as err:
            print("Passing double entries for {} (err: {}) ...".format(service, str(err)),
                  file=stderr)
        if len(service + ".csv") > 31:
            if args.verbose > 0:
                print("Service", service, "is", len(service + ".csv"), "length ; changing the name to:", service[len(service + ".csv") - 31:])
            csv_convert.convert_file(all_dic[service], "{}/{}.csv".format(args.output, service[len(service + ".csv") - 31:]))
        else:
            csv_convert.convert_file(all_dic[service], "{}/{}.csv".format(args.output, service))
    merge_all_to_a_book(glob.glob("{}/*.csv".format(args.output)), "{}/Listing_resources.xlsx".format(args.output))
