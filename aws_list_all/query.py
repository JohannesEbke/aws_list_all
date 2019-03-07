from __future__ import print_function

import json
import sys
from collections import defaultdict
from datetime import datetime
from multiprocessing.pool import ThreadPool
from random import shuffle

from .client import get_regions_for_service
from .introspection import get_listing_operations
from .listing import Listing

RESULT_NOTHING = '---'
RESULT_SOMETHING = '+++'
RESULT_ERROR = '!!!'

RESULT_IGNORE_ERRORS = {
    'apigateway': {
        # apigateway<->vpc links not supported in all regions
        'GetVpcLinks': 'vpc link not supported for region',
    },
    'autoscaling-plans': {
        # autoscaling-plans service not available in all advertised regions
        'DescribeScalingPlans': 'AccessDeniedException',
    },
    'config': {
        # config service not available in all advertised regions
        'DescribeConfigRules': 'AccessDeniedException',
    },
    'dynamodb': {
        # dynamodb Backups not available in all advertised regions
        'ListBackups': 'UnknownOperationException',
        # dynamodb Global Tables not available in all advertised regions
        'ListGlobalTables': 'UnknownOperationException',
    },
    'ec2': {
        # ec2 FPGAs not available in all advertised regions
        'DescribeFpgaImages': 'not valid for this web service',
    },
    'iot': {
        # full iot service not available in all advertised regions
        'DescribeAccountAuditConfiguration': ['An error occurred', 'No listing'],
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
    'lightsail': {
        # lightsail GetDomains only available in us-east-1
        'GetDomains': 'only available in the us-east-1',
    },
    'rekognition': {
        # rekognition stream processors not available in all advertised regions
        'ListStreamProcessors': 'AccessDeniedException',
    },
    'shield': {
        'DescribeDRTAccess': 'An error occurred',
        'DescribeEmergencyContactSettings': 'An error occurred',
    },
    'snowball': {
        'ListCompatibleImages': 'An error occurred',
    },
    'storagegateway': {
        # The storagegateway advertised but not available in some regions
        'DescribeTapeArchives': 'InvalidGatewayRequestException',
        'ListTapes': 'InvalidGatewayRequestException',
    },
    'xray': {
        'GetEncryptionConfig': 'No listing',
    },
}


def do_query(services, selected_regions=(), selected_operations=()):
    """For the given services, execute all selected operations (default: all) in selected regions
    (default: all)"""
    to_run = []
    for service in services:
        for region in get_regions_for_service(service, selected_regions):
            for operation in get_listing_operations(service, region, selected_operations):
                to_run.append([service, region, operation])
    shuffle(to_run)  # Distribute requests across endpoints
    results_by_type = defaultdict(list)
    for result in ThreadPool(32).imap_unordered(acquire_listing, to_run):
        results_by_type[result[0]].append(result)
        print(result[0][-1], end='')
        sys.stdout.flush()
    print()
    for result_type in (RESULT_NOTHING, RESULT_SOMETHING, RESULT_ERROR):
        for result in sorted(results_by_type[result_type]):
            print(*result)


def acquire_listing(what):
    """Given a service, region and operation execute the operation, serialize and save the result and
    return a tuple of strings describing the result."""
    service, region, operation = what
    try:
        listing = Listing.acquire(service, region, operation)
        if listing.resource_total_count > 0:
            with open("{}_{}_{}.json".format(service, operation, region), "w") as jsonfile:
                json.dump(listing.to_json(), jsonfile, default=datetime.isoformat)
            return (RESULT_SOMETHING, service, region, operation, ', '.join(listing.resource_types))
        else:
            return (RESULT_NOTHING, service, region, operation, ', '.join(listing.resource_types))
    except Exception as exc:  # pylint:disable=broad-except
        result_type = RESULT_ERROR

        ignored_err = RESULT_IGNORE_ERRORS.get(service, {}).get(operation)
        if ignored_err is not None:
            if not isinstance(ignored_err, list):
                ignored_err = list(ignored_err)
            for ignored_str_err in ignored_err:
                if ignored_str_err in str(exc):
                    result_type = RESULT_NOTHING

        if "is not supported in this region" in str(exc):
            result_type = RESULT_NOTHING
        if "is not available in this region" in str(exc):
            result_type = RESULT_NOTHING
        if "This request has been administratively disabled" in str(exc):
            result_type = RESULT_NOTHING
        return (result_type, service, region, operation, repr(exc))


def do_list_files(filenames, verbose=False):
    """Print out a rudimentary summary of the Listing objects contained in the given files"""
    for listing_filename in filenames:
        with open(listing_filename, "rb") as lst:
            listing = Listing.from_json(json.load(lst))
            resources = listing.resources
            for resource_type, value in resources.items():
                print(listing.service, listing.region, listing.operation, resource_type, len(value))
                if verbose:
                    for item in value:
                        idkey = None
                        if isinstance(item, dict):
                            for heuristic in [
                                lambda x: x == "id" or x.endswith("Id"),
                                lambda x: x == "SerialNumber",
                            ]:
                                idkeys = [k for k in item.keys() if heuristic(k)]
                                if idkeys:
                                    idkey = idkeys[0]
                                    break
                        if idkey:
                            print("    - ", item.get(idkey, ', '.join(item.keys())))
                        else:
                            print("    - ", item)
