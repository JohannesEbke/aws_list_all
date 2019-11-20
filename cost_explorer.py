from datetime import datetime
from argparse import ArgumentParser
from sys import stderr
import os
import json
import boto3

if __name__ == '__main__':
    parser = ArgumentParser(
        prog='cost_explorer',
        description=(
            'List AWS resources on one account across regions and services. '
            'Saves result into json files, which can then be passed to this tool again '
            'to list the contents.'
        )
    )
    parser.add_argument('-v', '--verbose', action='count',
                        help='Print detailed info during run')
    parser.add_argument('-a', '--arn', default=None,
                        help='Pass an ARN and get temporary credentials from it')
    parser.add_argument('-sn', '--session-name', default=None,
                        help='Name the session for the temporary credentials')
    parser.add_argument('-r', '--region', action='append',
                        help='Restrict querying to the given region (can be specified multiple times)')
    parser.add_argument('-ds', '--date-start', default='2019-01-01',
                        help='The starting date')
    parser.add_argument('-de', '--date-end', default='2019-02-01',
                        help='The ending date')
    parser.add_argument('-o', '--output-directory', default='.',
                        help='The directory to save the data')
    args = parser.parse_args()

    if (args.arn is None and args.session_name is not None) or (
            args.session_name is None and args.arn is not None):
        print("ARN and session name must be both given when one of them is passed.", file=stderr)
        exit(1)
    if args.arn is not None and args.session_name is not None:
        sts = boto3.Session(region_name=args.region).client('sts')
        credentials = sts.assume_role(RoleArn=args.arn,
                                      RoleSessionName=args.session_name)
        session = boto3.Session(region_name=args.region,
                             aws_access_key_id=credentials["Credentials"]["AccessKeyId"],
                             aws_secret_access_key=credentials["Credentials"]["SecretAccessKey"],
                             aws_session_token=credentials["Credentials"]["SessionToken"]).client('ce')
    else:
        session = boto3.Session(region_name=args.region).client('ce')
    costs_explorer = session.get_cost_and_usage(
        TimePeriod={'Start': args.date_start, 'End': args.date_end},
        Granularity='DAILY',
        Metrics=["AmortizedCost", "BlendedCost", "NetAmortizedCost",
                 "NetUnblendedCost", "UnblendedCost"])
    print("Creating dir '{}' if it doesn't exists...".format(args.output_directory))
    if not os.path.isdir(args.output_directory):
        os.mkdir(args.output_directory)
    print("Writing the output in file '{}'".format(args.output_directory + "/cost_explorer.json"))
    if args.session_name is not None:
        file_name = "{}/{}_cost_explorer.json".format(args.output_directory, args.session_name)
    else:
        file_name = "{}/cost_explorer.json".format(args.output_directory)
    with open(file_name, 'w') as jsonfile:
        json.dump(costs_explorer["ResultsByTime"], jsonfile, default=datetime.isoformat, indent=4)

    total = {"AmortizedCost": 0, "BlendedCost": 0, "NetAmortizedCost": 0,
             "NetUnblendedCost": 0, "UnblendedCost": 0}
    for result_idx in range(len(costs_explorer["ResultsByTime"])):
        for cost_type in costs_explorer["ResultsByTime"][result_idx]["Total"]:
            if costs_explorer["ResultsByTime"][result_idx]["Total"][cost_type]["Unit"] != "USD":
                continue
            total[cost_type] += float(costs_explorer["ResultsByTime"][result_idx]["Total"][cost_type]["Amount"])
    for each_total in total:
        print("~> Average cost for '%s': %.2f$." % (each_total, total[each_total] / len(costs_explorer["ResultsByTime"])))
