import json
import glob
from sys import stderr
from pandas.io.json import json_normalize
from aws_list_all.csv_convert import convert_file
from pyexcel.cookbook import merge_all_to_a_book


def make_unique_json():
    files_list = glob.glob("../data/*/*/*.json")
    print(files_list)
    # all_dic = dict(list())
    all_dic = dict()
    for file_path in files_list:
        service_name = file_path.split("/")[-1].replace(".json", "")
        print("Switching to service " + service_name + "..." + "from:",
              file_path)
        with open(file_path) as file:
            file_content = json.load(file)
            try:
                if service_name in all_dic:
                    all_dic.update(
                        {service_name: all_dic[service_name] + file_content})
                else:
                    all_dic.update({service_name: file_content})
            except TypeError:
                print("Passing ...", file=stderr)
            # all_dic[service_name]
            # print("Dict", all_dic)
            # for key in file_content:
            #     print("Key", key)
            # all_dic[service_name] = key
            # if key not in all_dic[service_name]:
            #     all_dic[service_name].append(key)
    print("Dic before removing double entries:", all_dic)
    for service in all_dic:
        try:
            all_dic[service] = [i for n, i in enumerate(all_dic[service]) if
                                i not in all_dic[service][n + 1:]]
        except TypeError:
            print("Passing double entries for {} ...".format(service),
                  file=stderr)
        # with open("../output/{}.json".format(service), "w+") as outfile:
        print(service)
        if len(service + ".csv") > 31:
            print("Service", service, "is", len(service + ".csv"), "length & modif:", service[len(service + ".csv") - 31:])
            convert_file(all_dic[service], "../output/{}.csv".format(service[len(service + ".csv") - 31:]))
        else:
            convert_file(all_dic[service], "../output/{}.csv".format(service))

        # for service_content in all_dic[service]:
        # print(all_dic[service])
    print(glob.glob("../output/*.csv"))
    merge_all_to_a_book(glob.glob("../output/*.csv"), "../Listing_resources.xlsx")
    print("The final dic is:", all_dic)
    # with open("../masterjson.json", "w+") as outfile:
    #     json.dump(all_dic, outfile)
    #     tablib.Dataset.

    # pandas.read_json("masterjson.json").to_excel("output.xlsx")
