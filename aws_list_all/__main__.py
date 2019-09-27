#!/usr/bin/env python
from __future__ import print_function

import glob
import os
from argparse import ArgumentParser
from resource import setrlimit, RLIMIT_NOFILE, getrlimit
from sys import exit, stderr
from pyexcel.cookbook import merge_all_to_a_book
from aws_list_all.merge import make_merge_json

from aws_list_all.introspection import (
    get_listing_operations, get_services, get_verbs,
    introspect_regions_for_service, recreate_caches
)
from aws_list_all.query import do_list_files, do_query


def increase_limit_nofiles():
    soft_limit, hard_limit = getrlimit(RLIMIT_NOFILE)
    desired_limit = 6000  # This should be comfortably larger than the product of services and regions
    if hard_limit < desired_limit:
        print("" * 80, file=stderr)
        print(
            "WARNING!\n"
            "Your system limits the number of open files and network connections to {}.\n"
            "This may lead to failures during querying.\n"
            "Please increase the hard limit of open files to at least {}.\n"
            "The configuration for hard limits is often found in /etc/security/limits.conf".format(
                hard_limit, desired_limit
            ),
            file=stderr
        )
        print("-" * 80, file=stderr)
        print(file=stderr)
    target_soft_limit = min(desired_limit, hard_limit)
    if target_soft_limit > soft_limit:
        print(
            "Increasing the open connection limit \"nofile\" from {} to {}.".format(
                soft_limit, target_soft_limit))
        setrlimit(RLIMIT_NOFILE, (target_soft_limit, hard_limit))
    print("")


def main():
    """Parse CLI arguments to either list services, operations, queries or existing json files"""
    parser = ArgumentParser(
        prog='aws_list_all',
        description=(
            'List AWS resources on one account across regions and services. '
            'Saves result into json files, which can then be passed to this tool again '
            'to list the contents.'
        )
    )
    subparsers = parser.add_subparsers(
        description='List of subcommands. Use <subcommand> --help for more parameters',
        dest='command',
        metavar='COMMAND'
    )
    generate = subparsers.add_parser("generate",
                                     description="Generate a master spreadsheet for a specific session name",
                                     help="You must enter the session name. You should have already generated .csv files")
    generate.add_argument("-s",
                          "--session-name",
                          help="The session's name that the program have to look for")
    generate.add_argument('-d', '--directory', default='.',
                          help='Directory to save the spreadsheet')

    merge = subparsers.add_parser("merge",
                          description="From all resources, remove the duplicate",
                          help="You should have already generated .json files")

    merge.add_argument("-d", "--directory", default=".", help="Directory where the data come from")
    merge.add_argument("-o", "--output", default="../output/", help="Directory where the generated general csv files")
    merge.add_argument('-v', '--verbose', action='count', default=0,
                       help='Print detailed info during run')
    # Query is the main subcommand, so we put it first
    query = subparsers.add_parser('query',
                                  description='Query AWS for resources',
                                  help='Query AWS for resources')
    query.add_argument(
        '-s',
        '--service',
        action='append',
        help='Restrict querying to the given service (can be specified multiple times)'
    )
    query.add_argument(
        '-r',
        '--region',
        action='append',
        help='Restrict querying to the given region (can be specified multiple times)'
    )

    query.add_argument(
        '-o',
        '--operation',
        action='append',
        help='Restrict querying to the given operation (can be specified multiple times)'
    )
    query.add_argument('-p', '--parallel', default=32, type=int,
                       help='Number of request to do in parallel')
    query.add_argument('-d', '--directory', default='.',
                       help='Directory to save result listings to')
    query.add_argument('-v', '--verbose', action='count',
                       help='Print detailed info during run')
    query.add_argument('-a', '--arn', default=None,
                       help='Pass an ARN and get temporary credentials from it')
    query.add_argument('-sn', '--session-name', default=None,
                       help='Name the session for the temporary credentials')

    # Once you have queried, show is the next most important command. So it comes second
    show = subparsers.add_parser(
        'show', description='Show a summary or details of a saved listing',
        help='Display saved listings'
    )

    show.add_argument('listingfile', nargs='*',
                      help='listing file(s) to load and print')
    show.add_argument('-v', '--verbose', action='count',
                      help='print given listing files with detailed info')

    # Introspection debugging is not the main function. So we put it all into a subcommand.
    introspect = subparsers.add_parser(
        'introspect',
        description='Print introspection debugging information',
        help='Print introspection debugging information'
    )
    introspecters = introspect.add_subparsers(
        description='Pieces of debug information to collect. Use <DETAIL> --help for more parameters',
        dest='introspect',
        metavar='DETAIL'
    )

    introspecters.add_parser(
        'list-services',
        description='Lists short names of AWS services that the current boto3 version has clients for.',
        help='List available AWS services'
    )
    introspecters.add_parser(
        'list-service-regions',
        description='Lists regions where AWS services are said to be available.',
        help='List AWS service regions'
    )
    ops = introspecters.add_parser(
        'list-operations',
        description='List all discovered listing operations on all (or specified) services',
        help='List discovered listing operations'
    )
    ops.add_argument(
        '-s',
        '--service',
        action='append',
        help='Only list discovered operations of the given service (can be specified multiple times)'
    )
    introspecters.add_parser('debug', description='Debug information',
                             help='Debug information')

    # Finally, refreshing the service/region caches comes last.
    subparsers.add_parser(
        'recreate-caches',
        description=(
            'Recreate the service/region availability caches, '
            'in case service availability changed since the last release'
        ),
        help='Recreate service caches'
    )

    args = parser.parse_args()

    if args.command == "merge":
        make_merge_json(args)
    elif args.command == "generate":
        if args.session_name is None:
            print("You must enter a session name", file=stderr)
            exit(1)
        if args.directory:
            try:
                os.makedirs(args.directory)
            except OSError:
                pass
            os.chdir(args.directory)
        all_files = glob.glob("*/{}/*.csv".format(args.session_name))
        for i in range(len(all_files)):
            all_files[i] = all_files[i].replace(args.session_name + "_", "")
        merge_all_to_a_book(all_files,
                            "Listing_{}.xlsx".format(args.session_name))
        print("Generation ended")
    elif args.command == 'query':
        if args.directory:
            try:
                os.makedirs(args.directory)
            except OSError:
                pass
            os.chdir(args.directory)
        increase_limit_nofiles()
        services = args.service or get_services()
        do_query(services, args, args.verbose or 0, args.parallel)
    elif args.command == 'show':
        if args.listingfile:
            increase_limit_nofiles()
            do_list_files(args.listingfile, verbose=args.verbose or 0)
        else:
            show.print_help()
            return 1
    elif args.command == 'introspect':
        if args.introspect == 'list-services':
            for service in get_services():
                print(service)
        elif args.introspect == 'list-service-regions':
            introspect_regions_for_service()
            return 0
        elif args.introspect == 'list-operations':
            for service in args.service or get_services():
                for operation in get_listing_operations(service):
                    print(service, operation)
        elif args.introspect == 'debug':
            for service in get_services():
                for verb in get_verbs(service):
                    print(service, verb)
        else:
            introspect.print_help()
            return 1
    elif args.command == 'recreate-caches':
        increase_limit_nofiles()
        recreate_caches()
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    exit(main())
