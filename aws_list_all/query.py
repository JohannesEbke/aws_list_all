from __future__ import print_function

import json
import sys
import contextlib
from collections import defaultdict
from datetime import datetime
from functools import partial
from multiprocessing.pool import ThreadPool
from os import chdir, listdir
from random import shuffle
from time import time
from traceback import print_exc

from .generate_html import (
    generate_header, generate_table, generate_time_footer, generate_compare_footer, html_doc_start, generate_file
)
from .introspection import get_listing_operations, get_regions_for_service
from .listing import RawListing, FilteredListing, ResultListing
from os.path import dirname

RESULT_NOTHING = '---'
RESULT_SOMETHING = '+++'
RESULT_ERROR = '!!!'
RESULT_NO_ACCESS = '>:|'

DIFF_NONE = 'same'
DIFF_NEW = 'added'
DIFF_DEL = 'deleted'

DEPENDENT_OPERATIONS = {
    'ListKeys': 'ListAliases',
    'DescribeInternetGateways': 'DescribeVpcs',
}

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
    'service-quotas': {
        'GetAssociationForServiceQuotaTemplate': 'TemplatesNotAvailableInRegionException',
        'ListServiceQuotaIncreaseRequestsInTemplate': 'TemplatesNotAvailableInRegionException',
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


def do_query(
    services, selected_regions=(), selected_operations=(), verbose=0, parallel=32, selected_profile=None, unfilter=()
):
    """For the given services, execute all selected operations (default: all) in selected regions
    (default: all)"""
    to_run = []
    dependencies = {}
    print('Building set of queries to execute...')
    for service in services:
        for region in get_regions_for_service(service, selected_regions):
            for operation in get_listing_operations(service, region, selected_operations, selected_profile):
                if verbose > 0:
                    region_name = region or 'n/a'
                    print('Service: {: <28} | Region: {:<15} | Operation: {}'.format(service, region_name, operation))
                if operation in DEPENDENT_OPERATIONS:
                    dependencies[DEPENDENT_OPERATIONS[operation], region] = [
                        service, region, DEPENDENT_OPERATIONS[operation], selected_profile, unfilter
                    ]
                if operation in DEPENDENT_OPERATIONS.values():
                    dependencies[operation, region] = [service, region, operation, selected_profile, unfilter]
                    continue

                to_run.append([service, region, operation, selected_profile, unfilter])
    shuffle(to_run)  # Distribute requests across endpoints
    results_by_type = defaultdict(list)
    print('...done. Executing queries...')

    results_by_type = execute_query(dependencies.values(), verbose, parallel, results_by_type)
    results_by_type = execute_query(to_run, verbose, parallel, results_by_type)
    print('...done')
    for result_type in (RESULT_NOTHING, RESULT_SOMETHING, RESULT_NO_ACCESS, RESULT_ERROR):
        for result in sorted(results_by_type[result_type]):
            print(*result.to_tuple)


def execute_query(to_run, verbose, parallel, results_by_type):
    """Execute the queries in the given list and save the results in the given dict sorted by result type"""
    # the `with` block is a workaround for a bug: https://bugs.python.org/issue35629
    with contextlib.closing(ThreadPool(parallel)) as pool:
        for result in pool.imap_unordered(partial(acquire_listing, verbose), to_run):
            results_by_type[result.result_type].append(result)
            if verbose > 1:
                print('ExecutedQueryResult: {}'.format(result.to_tuple))
            else:
                print(result.to_tuple[0][-1], end='')
                sys.stdout.flush()
    return results_by_type


def print_query(
    services, selected_regions=(), selected_operations=(), verbose=0, parallel=32, selected_profile=None, unfilter=()
):
    """For the given services, execute all selected operations (default: all) in selected regions
    (default: all) and display result in HTML-format"""
    to_run = []
    dependencies = {}
    for service in services:
        for region in get_regions_for_service(service, selected_regions):
            for operation in get_listing_operations(service, region, selected_operations, selected_profile):
                if verbose > 0:
                    region_name = region or 'n/a'
                    print('Service: {: <28} | Region: {:<15} | Operation: {}'.format(service, region_name, operation))
                if operation in DEPENDENT_OPERATIONS:
                    dependencies[DEPENDENT_OPERATIONS[operation], region] = [
                        service, region, DEPENDENT_OPERATIONS[operation], selected_profile, unfilter
                    ]
                if operation in DEPENDENT_OPERATIONS.values():
                    dependencies[operation, region] = [service, region, operation, selected_profile, unfilter]
                    continue

                to_run.append([service, region, operation, selected_profile, unfilter])
    shuffle(to_run)  # Distribute requests across endpoints
    results_by_type = defaultdict(list)
    results_by_region = defaultdict(lambda: defaultdict(list))
    services_in_grid = set()

    start = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT")

    results_by_type, results_by_region, services_in_grid = execute_html_query(
        dependencies.values(), verbose, parallel, results_by_type, results_by_region, services_in_grid
    )
    results_by_type, results_by_region, services_in_grid = execute_html_query(
        to_run, verbose, parallel, results_by_type, results_by_region, services_in_grid
    )

    fin = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S GMT")
    return (generate_header() + generate_table(results_by_region, services_in_grid) + generate_time_footer(start, fin))


def execute_html_query(to_run, verbose, parallel, typesorted, regionsorted, services):
    """Execute the queries in the given list and save the results in the given dictionaries
    sorted by result type and region"""
    with contextlib.closing(ThreadPool(parallel)) as pool:
        for result in pool.imap_unordered(partial(acquire_listing, verbose), to_run):
            typesorted[result.result_type].append(result)
            regionsorted[result.input.region][result.result_type].append(result)
            services.add(result.input.service)
            if verbose > 1:
                print('ExecutedQueryResult: {}'.format(result.to_tuple))
            else:
                sys.stdout.flush()
    return [typesorted, regionsorted, services]


def acquire_listing(verbose, what):
    """Given a service, region and operation execute the operation, serialize and save the result and
    return a tuple of strings describing the result."""
    service, region, operation, profile, unfilter = what
    start_time = time()
    try:
        if verbose > 1:
            print(what, 'starting request...')
        listing = RawListing.acquire(service, region, operation, profile)
        listingFile = FilteredListing(listing, './', unfilter)
        duration = time() - start_time
        if verbose > 1:
            print(what, '...request successful')
            print("timing [success]:", duration, what)
        with open('{}_{}_{}_{}.json'.format(service, operation, region, profile), 'w') as jsonfile:
            json.dump(listingFile.to_json(), jsonfile, default=datetime.isoformat)

        resource_count = listingFile.resource_total_count
        if listingFile.input.error == RESULT_ERROR:
            return ResultListing(listing, RESULT_ERROR, 'Error(Error during processing of resources)')
        if resource_count > 0:
            id_list = []
            for resource_type, value in listingFile.resources.items():
                id_list += verbose_list_files(resource_type, value)
            return ResultListing(listing, RESULT_SOMETHING, ', '.join(listingFile.resource_types), id_list)
        else:
            return ResultListing(listing, RESULT_NOTHING, ', '.join(listingFile.resource_types))
    except Exception as exc:  # pylint:disable=broad-except
        duration = time() - start_time
        if verbose > 1:
            print(what, '...exception:', exc)
            print("timing [failure]:", duration, what)
        if verbose > 2:
            print_exc()
        result_type = RESULT_NO_ACCESS if 'AccessDeniedException' in str(exc) else RESULT_ERROR

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

        listing = RawListing(service, region, operation, {}, profile, result_type)
        listingFile = FilteredListing(listing, './', unfilter)
        with open('{}_{}_{}_{}.json'.format(service, operation, region, profile), 'w') as jsonfile:
            json.dump(listingFile.to_json(), jsonfile, default=datetime.isoformat)
        return ResultListing(listing, result_type, repr(exc))


def show_list_files(
    filenames, orig_dir, cmp, html, verbose=0, not_found=False, errors=False, denied=False, unfilter=()
):
    """Print out a rudimentary summary of the Listing objects contained in the given files"""
    if cmp != '.':
        content = html_doc_start()
        content += compare_list_files(filenames, cmp)
        generate_file(orig_dir, 'cmp', content)
    elif html:
        content = html_doc_start()
        _, base_regionsorted, base_services = setup_table_headers(dirname(filenames[0]), filenames)
        content += generate_header()
        content += generate_table(base_regionsorted, base_services)
        generate_file(orig_dir, html, content)
    else:
        do_list_files(filenames, verbose, not_found, errors, denied, unfilter)


def compare_list_files(basefiles, modfiles):
    """Compare the saved listing-files from two directories and display the changes from base to mod
    in HTML-format"""
    basedir = dirname(basefiles[0])
    moddir = dirname(modfiles[0])
    base_typesorted, base_regionsorted, base_services = setup_table_headers(basedir, basefiles)
    mod_typesorted, mod_regionsorted, mod_services = setup_table_headers(moddir, modfiles)
    diff_regionsorted = defaultdict(lambda: defaultdict(list))
    diff_services = base_services.union(mod_services)

    for base_region in base_regionsorted:
        for result_type in base_regionsorted[base_region]:
            for listing in base_regionsorted[base_region][result_type]:
                if listing in mod_regionsorted[base_region][result_type]:
                    diff_regionsorted[base_region][result_type].append(ResultListing.diffInListing(listing, DIFF_NONE))
                    mod_regionsorted[base_region][result_type].remove(listing)
                else:
                    diff_regionsorted[base_region][result_type].append(ResultListing.diffInListing(listing, DIFF_DEL))

    for mod_region in mod_regionsorted:
        for result_type in mod_regionsorted[mod_region]:
            for listing in mod_regionsorted[mod_region][result_type]:
                diff_regionsorted[mod_region][result_type].append(ResultListing.diffInListing(listing, DIFF_NEW))

    return (
        generate_header() + generate_table(diff_regionsorted, diff_services) + generate_compare_footer(basedir, moddir)
    )


def setup_table_headers(dir, filenames):
    """Read the listing results from a given directory and return them inside dictionaries
    sorted by result type and region"""
    typesorted = defaultdict(list)
    regionsorted = defaultdict(lambda: defaultdict(list))
    services = set()
    for listing_filename in filenames:
        read_file = FilteredListing.from_json(json.load(open(listing_filename, 'rb')))
        listing = RawListing.from_json(json.load(open(listing_filename, 'rb')))
        listing_entry = FilteredListing(listing, dir, read_file.unfilter)
        id_list = []
        if listing_entry.resource_total_count > 0:
            for resource_type, value in listing_entry.resources.items():
                id_list += verbose_list_files(resource_type, value)
        result = ResultListing(listing_entry.input, listing_entry.result_type, '', id_list)
        typesorted[result.result_type].append(result)
        regionsorted[result.input.region][result.result_type].append(result)
        services.add(result.input.service)
    return [typesorted, regionsorted, services]


def do_list_files(filenames, verbose=0, not_found=False, errors=False, denied=False, unfilter=()):
    """Print out a rudimentary summary of the Listing objects contained in the given files"""
    dir = dirname(filenames[0])
    for listing_filename in filenames:
        read_file = FilteredListing.from_json(json.load(open(listing_filename, 'rb')))
        combined_unf = read_file.unfilter if unfilter is None else (read_file.unfilter + unfilter)
        listing = RawListing.from_json(json.load(open(listing_filename, 'rb')))
        listing_entry = FilteredListing(listing, dir, combined_unf)
        resources = listing_entry.resources

        truncated = False
        was_denied = False
        if 'truncated' in resources:
            truncated = resources['truncated']
            del resources['truncated']
        if listing.error == RESULT_NO_ACCESS:
            was_denied = True
            if not resources and denied:
                print(listing.service, listing.region, listing.operation, 'MISSING PERMISSION', '0')
        if listing.error == RESULT_ERROR and errors:
            print(listing.service, listing.region, listing.operation, 'ERROR', '0')
        if listing.error == RESULT_ERROR and listing_entry.resource_total_count > 0:
            continue

        for resource_type, value in resources.items():
            if not not_found and len(value) == 0 and not was_denied:
                continue
            if not denied and was_denied:
                continue
            if was_denied:
                resource_type = 'MISSING PERMISSION'
            len_string = '> {}'.format(len(value)) if truncated else str(len(value))
            print(listing.service, listing.region, listing.operation, resource_type, len_string)
            if verbose > 0:
                id_list = verbose_list_files(resource_type, value)
                for resource_id in id_list:
                    print('    - ', resource_id)
                if truncated:
                    print('    - ... (more items, query truncated)')


def verbose_list_files(resource_type, value):
    """Search and return a list of the resource IDs from a listing-response entry"""
    IDs = []
    for item in value:
        idkey = None
        if isinstance(item, dict):
            guesses = [resource_type[:-1] + "Id", "id", "SerialNumber"]
            # Find the last uppercase word in the resource_type and construct some guesses from that
            uppercase_indices = [i for (i, c) in enumerate(resource_type) if c.isupper()]
            if uppercase_indices:
                last_word_in_resource_type = resource_type[uppercase_indices[-1]:]
                guesses.append(last_word_in_resource_type[:-1] + "Id")
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
                    idkeys = [k for k in item.keys() if heuristic(k)]
                    if idkeys:
                        # Heuristic: Shortest ID is probably the Resource ID
                        idkeys.sort(key=len)
                        idkey = idkeys[0]
                        break
        if idkey:
            IDs.append(item.get(idkey, ', '.join(item.keys())))
        else:
            IDs.append(item)

    return IDs


def do_consecutive(
    services,
    orig_dir,
    directory,
    html,
    selected_regions=(),
    selected_operations=(),
    verbose=0,
    parallel=32,
    selected_profile=None,
    unfilter=(),
    not_found=False,
    errors=False,
    denied=False
):
    """Execute a query and print out the summarized results in succession or display them in HTML format"""
    if html:
        content = html_doc_start()
        content += print_query(
            services, selected_regions, selected_operations, verbose, parallel, selected_profile, unfilter
        )
        generate_file(orig_dir, html, content)
    else:
        do_query(services, selected_regions, selected_operations, verbose, parallel, selected_profile, unfilter)
        chdir(orig_dir)
        filenames = []
        for fn in listdir(directory):
            filenames.append(directory.replace('./', '') + fn)
        print('\n-------------------- Summary of saved listings --------------------\n')
        do_list_files(filenames, verbose, not_found, errors, denied, unfilter)
