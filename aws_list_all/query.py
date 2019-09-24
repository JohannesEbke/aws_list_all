from __future__ import print_function

import json
import sys
import contextlib
from collections import defaultdict
from datetime import datetime
from functools import partial
from multiprocessing.pool import ThreadPool
from random import shuffle
from traceback import print_exc
import os.path
from pyexcel.cookbook import merge_all_to_a_book
import glob

from .introspection import get_listing_operations, get_regions_for_service
from .listing import Listing
from .csv_convert import convert_file

import boto3

RESULT_NOTHING = '---'
RESULT_SOMETHING = '+++'
RESULT_ERROR = '!!!'
RESULT_NO_ACCESS = '>:|'

# List of requests with legitimate, persistent errors that indicate that no listable resources are present.
#
# If the request would never return listable resources, it should not be done and be listed in one of the lists
# in introspection.py.
#
# TODO: If the error just indicates that the current user does not have the permissions to list resources,
# the user of this tool should probably be warned.
RESULT_IGNORE_ERRORS = {
    'apigateway': {
        # apigateway<->vpc links not supported in all regions
        'GetVpcLinks': 'vpc link not supported for region',
    },
    'autoscaling-plans': {
        # autoscaling-plans service not available in all advertised regions
        'DescribeScalingPlans': 'AccessDeniedException',
    },
    'backup': {
        'GetSupportedResourceTypes': 'AccessDeniedException',
    },
    'cloud9': {
        # Cloud9 has DNS entries for endpoints in some regions, but does not serve the right certificate
        'ListEnvironments': 'SSLError',
        'DescribeEnvironmentMemberships': 'SSLError',
    },
    'cloudhsm': {
        'ListHapgs': 'This service is unavailable.',
        'ListLunaClients': 'This service is unavailable.',
        'ListHsms': 'This service is unavailable.',
    },
    'config': {
        # config service not available in all advertised regions
        'DescribeConfigRules': 'AccessDeniedException',
    },
    'cur': {
        # Linked accounts are not authorized to describe report definitions
        'DescribeReportDefinitions': 'is not authorized to callDescribeReportDefinitions',
    },
    'directconnect': {
        'DescribeInterconnects': 'not an authorized Direct Connect partner.',
    },
    'dynamodb': {
        # dynamodb Backups not available in all advertised regions
        'ListBackups': 'UnknownOperationException',
        # dynamodb Global Tables not available in all advertised regions
        'ListGlobalTables': 'UnknownOperationException',
    },
    'ec2': {
        # ec2 FPGAs not available in all advertised regions
        'DescribeFpgaImages':
            'not valid for this web service',
        # Need to register as a seller to get this listing
        'DescribeReservedInstancesListings':
            'not authorized to use the requested product. Please complete the seller registration',
        # This seems to be the error if no ClientVpnEndpoints are available in the region
        'DescribeClientVpnEndpoints':
            'InternalError',
    },
    'fms': {
        'ListMemberAccounts': 'not currently delegated by AWS FM',
        'ListPolicies': 'not currently delegated by AWS FM',
    },
    'iot': {
        # full iot service not available in all advertised regions
        'DescribeAccountAuditConfiguration': ['An error occurred',
                                              'No listing'],
        'ListActiveViolations': 'An error occurred',
        'ListIndices': 'An error occurred',
        'ListJobs': 'An error occurred',
        'ListOTAUpdates': 'An error occurred',
        'ListScheduledAudits': 'An error occurred',
        'ListSecurityProfiles': 'An error occurred',
        'ListStreams': 'An error occurred',
    },
    'iotanalytics': {
        'DescribeLoggingOptions': 'An error occurred',
    },
    'license-manager': {
        'GetServiceSettings': 'Service role not found',
        'ListLicenseConfigurations': 'Service role not found',
        'ListResourceInventory': 'Service role not found',
    },
    'lightsail': {
        # lightsail GetDomains only available in us-east-1
        'GetDomains': 'only available in the us-east-1',
    },
    'machinelearning': {
        'DescribeBatchPredictions': 'AmazonML is no longer available to new customers.',
        'DescribeDataSources': 'AmazonML is no longer available to new customers.',
        'DescribeEvaluations': 'AmazonML is no longer available to new customers.',
        'DescribeMLModels': 'AmazonML is no longer available to new customers.',
    },
    'macie': {
        'ListMemberAccounts': 'Macie is not enabled',
        'ListS3Resources': 'Macie is not enabled',
    },
    'mturk': {
        'GetAccountBalance': 'Your AWS account must be linked to your Amazon Mechanical Turk Account',
        'ListBonusPayments': 'Your AWS account must be linked to your Amazon Mechanical Turk Account',
        'ListHITs': 'Your AWS account must be linked to your Amazon Mechanical Turk Account',
        'ListQualificationRequests': 'Your AWS account must be linked to your Amazon Mechanical Turk Account',
        'ListReviewableHITs': 'Your AWS account must be linked to your Amazon Mechanical Turk Account',
        'ListWorkerBlocks': 'Your AWS account must be linked to your Amazon Mechanical Turk Account',
    },
    'organizations': {
        'DescribeOrganization': 'AccessDeniedException',
        'ListAWSServiceAccessForOrganization': 'AccessDeniedException',
        'ListAccounts': 'AccessDeniedException',
        'ListCreateAccountStatus': 'AccessDeniedException',
        'ListHandshakesForOrganization': 'AccessDeniedException',
        'ListRoots': 'AccessDeniedException',
    },
    'rds': {
        'DescribeGlobalClusters': 'Access Denied to API Version',
    },
    'rekognition': {
        # rekognition stream processors not available in all advertised regions
        'ListStreamProcessors': 'AccessDeniedException',
    },
    'robomaker': {
        # ForbiddenException is raised if robomaker is not available in a region
        'ListDeploymentJobs': 'ForbiddenException',
        'ListFleets': 'ForbiddenException',
        'ListRobotApplications': 'ForbiddenException',
        'ListRobots': 'ForbiddenException',
        'ListSimulationApplications': 'ForbiddenException',
        'ListSimulationJobs': 'ForbiddenException',
    },
    'servicecatalog': {
        'GetAWSOrganizationsAccessStatus': 'AccessDeniedException',
    },
    'ses': {
        'DescribeActiveReceiptRuleSet': 'Service returned the HTTP status code: 404',
        'ListReceiptFilters': 'Service returned the HTTP status code: 404',
        'ListReceiptRuleSets': 'Service returned the HTTP status code: 404',
    },
    'shield': {
        'DescribeDRTAccess': 'An error occurred',
        'DescribeEmergencyContactSettings': 'An error occurred',
        'ListProtections': 'ResourceNotFoundException',
    },
    'snowball': {
        'ListCompatibleImages': 'An error occurred',
    },
    'storagegateway': {
        # The storagegateway advertised but not available in some regions
        'DescribeTapeArchives': 'InvalidGatewayRequestException',
        'ListTapes': 'InvalidGatewayRequestException',
    },
}

NOT_AVAILABLE_FOR_REGION_STRINGS = [
    'is not supported in this region',
    'is not available in this region',
    'not supported in the called region.',
    'Operation not available in this region',
    'Credential should be scoped to a valid region,',
    'The security token included in the request is invalid.',
    'AWS was not able to validate the provided access credentials',
    'InvalidAction',
]

NOT_AVAILABLE_FOR_ACCOUNT_STRINGS = [
    'This request has been administratively disabled',
    'Your account isn\'t authorized to call this operation.',
    'AWS Premium Support Subscription is required',
    'not subscribed to AWS Security Hub',
    'is not authorized to use this service',
    'Account not whitelisted',
]

NOT_AVAILABLE_STRINGS = NOT_AVAILABLE_FOR_REGION_STRINGS + NOT_AVAILABLE_FOR_ACCOUNT_STRINGS


def do_query(services, args, selected_regions=(), selected_operations=(), verbose=0,
             parallel=32):
    """For the given services, execute all selected operations (default: all) in selected regions
    (default: all)"""
    to_run = []
    if (args.arn is None and args.name is not None) or (args.name is None and args.arn is not None):
        print("Err: session name is given but no ARN has been set")
        exit(1)
    print('Building set of queries to execute...')
    for service in services:
        for region in get_regions_for_service(service, selected_regions):
            for operation in get_listing_operations(service, region, args.arn, args.name, selected_operations):
                if region is None:
                    print("{} has a none region".format(service))
                    continue
                if verbose > 0:
                    print(
                        'Service: {: <28} | Region: {:<15} | Operation: {}'.format(
                            service, region, operation))
                to_run.append([service, region, operation])
    shuffle(to_run)  # Distribute requests across endpoints
    results_by_type = defaultdict(list)
    print('...done. Executing queries...')
    # the `with` block is a workaround for a bug: https://bugs.python.org/issue35629
    with contextlib.closing(ThreadPool(parallel)) as pool:
        for result in pool.imap_unordered(partial(acquire_listing, verbose, args.name),
                                          to_run):
            results_by_type[result[0]].append(result)
            # print(result[3])
            if verbose > 1:
                print('ExecutedQueryResult: {}'.format(result))
            else:
                print(result[0][-1], end='')
                sys.stdout.flush()
    print('...done\nGenerating a master spreadsheet...')
    merge_all_to_a_book(glob.glob("*/*.csv"), "Listing_{}.xlsx".format(args.name) if args.name is not None else "Listing.xlsx")
    print("Results:")
    for result_type in (RESULT_NOTHING, RESULT_SOMETHING, RESULT_NO_ACCESS, RESULT_ERROR):
        for result in sorted(results_by_type[result_type]):
            print(*result)


def extract_identifier(data):
    false_identifier = {"ResponseMetadata",
                        "Owner"}
    for data_key in data:
        if data_key not in false_identifier:
            return data_key
    return ""


def format_file_name(service, operation, session_name):
    known_prefix = {"Describe", "List"}
    for prefix in known_prefix:
        if prefix in operation:
            return "{}/{}_{}.json".format(service, session_name,
                                       str(operation).replace(prefix, ""))
    return "{}/{}_{}.json".format(service, session_name, operation)


def acquire_listing(verbose, session_name, what):
    """Given a service, region and operation execute the operation, serialize and save the result and
    return a tuple of strings describing the result."""
    # print("what?", what)
    service, region, operation = what
    try:
        if verbose > 1:
            print(what, 'starting request...')
        listing = Listing.acquire(service, region, operation)
        if verbose > 1:
            print(what, '...request successful.')
        if listing.resource_total_count > 0:
            file_name = format_file_name(service, operation, session_name)
            file_content = listing.to_json()["response"][
                extract_identifier(listing.to_json()["response"])]
            if not os.path.isdir(service):
                os.mkdir(service)
            with open(file_name, 'w') as jsonfile:
                json.dump(file_content, jsonfile, default=datetime.isoformat,
                          indent=4)
            convert_file(file_content, str(file_name).replace(".json", ".csv"))
            return RESULT_SOMETHING, service, region, operation, ', '.join(
                listing.resource_types)
        else:
            return RESULT_NOTHING, service, region, operation, ', '.join(
                listing.resource_types)
    except Exception as exc:  # pylint:disable=broad-except
        if verbose > 1:
            print(what, '...exception:', exc)
        if verbose > 2:
            print_exc()
        result_type = RESULT_NO_ACCESS if 'AccessDeniedException' in str(
            exc) else RESULT_ERROR

        ignored_err = RESULT_IGNORE_ERRORS.get(service, {}).get(operation)
        if ignored_err is not None:
            if not isinstance(ignored_err, list):
                ignored_err = list(ignored_err)
            for ignored_str_err in ignored_err:
                if ignored_str_err in str(exc):
                    result_type = RESULT_NOTHING

        for not_available_string in NOT_AVAILABLE_STRINGS:
            if not_available_string in str(exc):
                result_type = RESULT_NOTHING

        return result_type, service, region, operation, repr(exc)


def do_list_files(filenames, verbose=0):
    """Print out a rudimentary summary of the Listing objects contained in the given files"""
    for listing_filename in filenames:
        listing = Listing.from_json(json.load(open(listing_filename, 'rb')))
        resources = listing.resources
        truncated = False
        if 'truncated' in resources:
            truncated = resources['truncated']
            del resources['truncated']
        for resource_type, value in resources.items():
            len_string = '> {}'.format(len(value)) if truncated else str(
                len(value))
            print(listing.service, listing.region, listing.operation,
                  resource_type, len_string)
            if verbose > 0:
                for item in value:
                    idkey = None
                    if isinstance(item, dict):
                        guesses = [resource_type[:-1] + "Id", "id",
                                   "SerialNumber"]
                        # Find the last uppercase word in the resource_type and construct some guesses from that
                        uppercase_indices = [i for (i, c) in
                                             enumerate(resource_type) if
                                             c.isupper()]
                        if uppercase_indices:
                            last_word_in_resource_type = resource_type[
                                                         uppercase_indices[-1]:]
                            guesses.append(
                                last_word_in_resource_type[:-1] + "Id")
                            guesses.append(last_word_in_resource_type + "Id")
                        for guess in guesses:
                            if guess in item:
                                idkey = guess
                                break
                        if idkey is None:
                            for heuristic in [
                                lambda x: x.endswith('Id'),
                                lambda x: x.endswith('Name'),
                            ]:
                                idkeys = [k for k in item.keys() if
                                          heuristic(k)]
                                if idkeys:
                                    # Heuristic: Shortest ID is probably the Resource ID
                                    idkeys.sort(key=len)
                                    idkey = idkeys[0]
                                    break
                    if idkey:
                        print('    - ', item.get(idkey, ', '.join(item.keys())))
                    else:
                        print('    - ', item)
                if truncated:
                    print('    - ... (more items, query truncated)')
