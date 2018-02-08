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


def do_query(services, selected_regions=(), selected_operations=()):
    """For the given services, execute all selected operations (default: all) in selected regions
    (default: all)"""
    to_run = []
    for service in services:
        for region in selected_regions or get_regions_for_service(service):
            for operation in selected_operations or get_listing_operations(service):
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
        if service == 'storagegateway' and 'InvalidGatewayRequestException' in str(exc):
            # The storagegateway advertised but not available in some regions
            result_type = RESULT_NOTHING
        if service == 'config' and operation == 'DescribeConfigRules' \
                and 'AccessDeniedException' in str(exc):
            # The config service is advertised but not available in some regions
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
        listing = Listing.from_json(json.load(open(listing_filename, "rb")))
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
