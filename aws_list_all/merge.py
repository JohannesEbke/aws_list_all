import json
import glob
import os
from sys import stderr
from aws_list_all.csv_convert import convert_file
from pyexcel.cookbook import merge_all_to_a_book


def make_merge_json(args):
    try:
        os.makedirs(args.output)
    except OSError:
        pass
    if args.session_name is not None:
        files_list = glob.glob("{}/*/{}/*.json".format(args.directory, args.session_name))
    else:
        files_list = glob.glob("{}/*/*.json".format(args.directory, args.session_name))
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
            file_content = json.load(file)
            try:
                if service_name in all_dic:
                    if args.verbose > 1:
                        print("=> Service {} (from '{}') is already in the resume, adding the additional content...".format(service_name, file_path))
                    all_dic.update(
                        {service_name: all_dic[service_name] + file_content})
                else:
                    all_dic.update({service_name: file_content})
            except TypeError:
                print("Passing service {} (from '{}') because of a TypeError and cannot be added the all resources...".format(service_name, file_path), file=stderr)
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
            convert_file(all_dic[service], "{}/{}.csv".format(args.output, service[len(service + ".csv") - 31:]))
        else:
            convert_file(all_dic[service], "{}/{}.csv".format(args.output, service))
    merge_all_to_a_book(glob.glob("{}/*.csv".format(args.output)), "Listing_resources.xlsx")
