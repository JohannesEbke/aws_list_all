#!/usr/bin/env python
# pylint: disable=import-error
"""Module providing listing functions for all AWS services using boto3"""
from __future__ import print_function

import json
import pprint
import re
import os
import sys
from random import shuffle
from multiprocessing.pool import ThreadPool
from collections import defaultdict
from datetime import datetime

import boto3

try:
    raw_input
except NameError:
    raw_input = input

RESULT_NOTHING = '---'
RESULT_SOMETHING = '+++'
RESULT_ERROR = '!!!'

SERVICE_BLACKLIST = [
    'cur',  # costs and usage reports
    'discovery',  # requires manual whitelisting
    'support',  # support has no payable resources
]

DEPRECATED_OR_DISALLOWED = {
    'directconnect': ['DescribeInterconnects'],  # needs opt-in
    'ec2': ['DescribeScheduledInstances', 'DescribeReservedInstancesListings'],  # needs opt-in
    'emr': ['DescribeJobFlows'],  # deprecated
    'iam': ['GetCredentialReport'],  # credential report needs to be created
}

DISALLOWED_FOR_IAM_USERS = {
    'iam': [
        "ListAccessKeys", "ListMFADevices", "ListSSHPublicKeys", "ListServiceSpecificCredentials",
        "ListSigningCertificates"
    ],
    'importexport': ["ListJobs"],
}
# DEPRECATED_OR_DISALLOWED.update(DISALLOWED_FOR_IAM_USERS)

AWS_RESOURCE_QUERIES = {
    'apigateway': ['GetSdkTypes'],
    'autoscaling': [
        'DescribeAdjustmentTypes', 'DescribeTerminationPolicyTypes', 'DescribeAutoScalingNotificationTypes',
        'DescribeScalingProcessTypes', 'DescribeMetricCollectionTypes', 'DescribeLifecycleHookTypes'
    ],
    'cloudhsm': ['ListAvailableZones'],
    'cloudtrail': ['ListPublicKeys'],
    'codebuild': ['ListCuratedEnvironmentImages'],
    'codedeploy': ['ListDeploymentConfigs'],
    'codepipeline': ['ListActionTypes'],
    'devicefarm': ['ListDevices', 'ListOfferings', 'ListOfferingTransactions'],
    'directconnect': ['DescribeLocations'],
    'dms': ['DescribeEndpointTypes', 'DescribeOrderableReplicationInstances'],
    'ec2': [
        'DescribePrefixLists', 'DescribeAvailabilityZones', 'DescribeVpcEndpointServices', 'DescribeSpotPriceHistory',
        'DescribeHostReservationOfferings', 'DescribeRegions', 'DescribeReservedInstancesOfferings', 'DescribeIdFormat',
        'DescribeVpcClassicLinkDnsSupport'
    ],
    'elasticache': ['DescribeCacheParameterGroups', 'DescribeCacheEngineVersions'],
    'elasticbeanstalk': ['ListAvailableSolutionStacks', 'PlatformSummaryList'],
    'elastictranscoder': ['ListPresets'],
    'elb': ['DescribeLoadBalancerPolicyTypes', 'DescribeLoadBalancerPolicies'],
    'elbv2': ['DescribeSSLPolicies'],
    'inspector': ['ListRulesPackages'],
    'lex-models': ['GetBuiltinIntents'],
    'lightsail': ['GetBlueprints', 'GetBundles', 'GetRegions'],
    'polly': ['DescribeVoices'],
    'rds': ['DescribeDBEngineVersions', 'DescribeSourceRegions', 'DescribeCertificates', 'DescribeEventCategories'],
    'redshift': [
        'DescribeClusterVersions', 'DescribeReservedNodeOfferings', 'DescribeOrderableClusterOptions',
        'DescribeEventCategories'
    ],
    'route53': ['GetCheckerIpRanges', 'ListGeoLocations'],
    'ssm': ['DescribeAvailablePatches', 'GetInventorySchema'],
}

NOT_RESOURCE_DESCRIPTIONS = {
    'apigateway': ['GetAccount'],
    'autoscaling': ['DescribeAccountLimits'],
    'cloudformation': ['DescribeAccountLimits'],
    'cloudwatch': ['DescribeAlarmHistory'],
    'codebuild': ['ListBuilds'],
    'config': [
        'GetComplianceSummaryByResourceType', 'GetComplianceSummaryByConfigRule', 'DescribeComplianceByConfigRule',
        'DescribeComplianceByResource', 'DescribeConfigRuleEvaluationStatus'
    ],
    'devicefarm': ['GetAccountSettings', 'GetOfferingStatus'],
    'dms': ['DescribeAccountAttributes'],
    'ds': ['GetDirectoryLimits'],
    'dynamodb': ['DescribeLimits'],
    'ec2': [
        'DescribeAccountAttributes', 'DescribeDhcpOptions', 'DescribeVpcClassicLink', 'DescribeVpcClassicLinkDnsSupport'
    ],
    'ecr': ['GetAuthorizationToken'],
    'elasticache': ['DescribeReservedCacheNodesOfferings'],
    'elasticbeanstalk': ['DescribeEvents'],
    'elb': ['DescribeAccountLimits'],
    'elbv2': ['DescribeAccountLimits'],
    'es': ['ListElasticsearchVersions'],
    'gamelift': ['DescribeEC2InstanceLimits'],
    'iam': ['GetAccountPasswordPolicy', 'GetAccountSummary', 'GetUser', 'GetAccountAuthorizationDetails'],
    'inspector': ['DescribeCrossAccountAccessRole'],
    'iot': ['GetRegistrationCode', 'DescribeEndpoint'],
    'kinesis': ['DescribeLimits'],
    'lambda': ['GetAccountSettings'],
    'opsworks': ['DescribeMyUserProfile', 'DescribeUserProfiles'],
    'opsworkscm': ['DescribeAccountAttributes'],
    'rds': ['DescribeAccountAttributes', 'DescribeDBEngineVersions', 'DescribeReservedDBInstancesOfferings'],
    'route53': ['GetTrafficPolicyInstanceCount', 'GetHostedZoneCount', 'GetHealthCheckCount', 'GetGeoLocation'],
    'ses': ['GetSendQuota'],
    'sms': ['GetServers'],
    'snowball': ['GetSnowballUsage'],
    'sns': ['GetSMSAttributes', 'ListPhoneNumbersOptedOut'],
    'ssm': ['GetDefaultPatchBaseline'],
    'sts': ['GetSessionToken', 'GetCallerIdentity'],
    'waf': ['GetChangeToken'],
    'waf-regional': ['GetChangeToken'],
}

PARAMETERS_REQUIRED = {
    'cloudformation': ['GetTemplateSummary', 'DescribeStackResources', 'DescribeStackEvents', 'GetTemplate'],
    'cloudhsm': ['DescribeHsm', 'DescribeLunaClient'],
    'cloudtrail': ['GetEventSelectors'],
    'codecommit': ['GetBranch'],
    'cognito-idp': ['GetUser'],
    'ec2': ['DescribeSpotDatafeedSubscription'],
    'ecs': ['ListContainerInstances', 'ListServices', 'ListTasks'],
    'efs': ['DescribeMountTargets'],
    'elasticache': ['ListAllowedNodeTypeModifications', 'DescribeCacheSecurityGroups'],
    'elasticbeanstalk': [
        'DescribeEnvironmentManagedActionHistory', 'DescribeEnvironmentResources', 'DescribeEnvironmentManagedActions',
        'DescribeEnvironmentHealth', 'DescribeInstancesHealth', 'DescribeConfigurationOptions',
        'DescribePlatformVersion'
    ],
    'elbv2': ['DescribeRules', 'DescribeListeners'],
    'gamelift': ['DescribeGameSessionDetails', 'DescribeGameSessions', 'DescribePlayerSessions'],
    'health': ['DescribeEventTypes', 'DescribeEntityAggregates', 'DescribeEvents'],
    'iot': ['GetLoggingOptions'],
    'opsworks': [
        'DescribeAgentVersions', 'DescribeApps', 'DescribeCommands', 'DescribeDeployments', 'DescribeEcsClusters',
        'DescribeElasticIps', 'DescribeElasticLoadBalancers', 'DescribeInstances', 'DescribeLayers',
        'DescribePermissions', 'DescribeRaidArrays', 'DescribeVolumes'
    ],
    'redshift': ['DescribeTableRestoreStatus', 'DescribeClusterSecurityGroups'],
    'route53domains': ['GetContactReachabilityStatus'],
    'shield': ['DescribeSubscription', 'ListProtections'],
    'ssm': ['DescribeAssociation'],
}

PARAMETERS = {
    'ec2': {
        'DescribeSnapshots': {
            'OwnerIds': ['self']
        },
        'DescribeImages': {
            'Owners': ['self']
        },
    },
    'elasticbeanstalk': {
        'ListPlatformVersions': {
            'Filters': [{
                'Operator': '=',
                'Type': 'PlatformOwner',
                'Values': ['self']
            }]
        }
    },
    'iam': {
        'ListPolicies': {
            'Scope': 'Local'
        },
    },
    'ssm': {
        'ListDocuments': {
            'DocumentFilterList': [{
                'key': 'Owner',
                'value': 'self'
            }]
        },
    },
}

ssf = list(
    boto3.Session(
        region_name="us-east-1"
    ).client("cloudformation").meta.service_model.shape_for("ListStacksInput").members["StackStatusFilter"].member.enum
)
ssf.remove("DELETE_COMPLETE")
PARAMETERS.setdefault("cloudformation", {})["ListStacks"] = {"StackStatusFilter": ssf}

VERBS_LISTINGS = ['Describe', 'Get', 'List']


def get_services():
    """Return a list of all service names where listable resources can be present"""
    return [service for service in boto3.Session().get_available_services() if service not in SERVICE_BLACKLIST]


def get_regions_for_service(service):
    """Given a service name, return a list of region names where this service can have resources"""
    if service == "s3":
        return ['us-east-1']  # s3 ListBuckets is a global request, so no region required.
    return boto3.Session().get_available_regions(service) or [None]


CLIENTS = {}


def get_client(service, region=None):
    """Return (cached) boto3 clients for this service and this region"""
    if not region:
        region = get_regions_for_service(service)[0]
    if (service, region) not in CLIENTS:
        CLIENTS[(service, region)] = boto3.Session(region_name=region).client(service)
    return CLIENTS[(service, region)]


def get_verbs(client):
    """Return a list of "Verbs" given a boto3 service client. A "Verb" in this context is
    the first CamelCased word in an API call"""
    return set(re.sub("([A-Z])", "_\\1", x).split("_")[1] for x in client.meta.method_to_api_mapping.values())


def get_listing_operations(service):
    """Return a list of API calls which (probably) list resources created by the user
    in the given service (in contrast to AWS-managed or default resources)"""
    client = get_client(service)
    operations = []
    for operation in client.meta.service_model.operation_names:
        if not any(operation.startswith(prefix) for prefix in VERBS_LISTINGS):
            continue
        op_model = client.meta.service_model.operation_model(operation)
        if op_model.input_shape and op_model.input_shape.required_members:
            continue
        if operation in PARAMETERS_REQUIRED.get(service, []):
            continue
        if operation in AWS_RESOURCE_QUERIES.get(service, []):
            continue
        if operation in NOT_RESOURCE_DESCRIPTIONS.get(service, []):
            continue
        if operation in DEPRECATED_OR_DISALLOWED.get(service, []):
            continue
        operations.append(operation)
    return operations


def run_raw_listing_operation(service, region, operation):
    """Execute a given operation and return its raw result"""
    client = get_client(service, region)
    api_to_method_mapping = dict((v, k) for k, v in client.meta.method_to_api_mapping.items())
    parameters = PARAMETERS.get(service, {}).get(operation, {})
    return getattr(client, api_to_method_mapping[operation])(**parameters)


class Listing(object):
    """Represents a listing operation on an AWS service and its result"""

    def __init__(self, service, region, operation, response):
        self.service = service
        self.region = region
        self.operation = operation
        self.response = response

    def to_json(self):
        return {
            'service': self.service,
            'region': self.region,
            'operation': self.operation,
            'response': self.response,
        }

    @classmethod
    def from_json(cls, data):
        return cls(
            service=data.get('service'),
            region=data.get('region'),
            operation=data.get('operation'),
            response=data.get('response')
        )

    @property
    def resource_types(self):
        """The list of resource types (Keys with list content) in the response"""
        return list(self.resources.keys())

    @property
    def resource_total_count(self):
        """The estimated total count of resources - can be incomplete"""
        return sum(len(v) for v in self.resources.values())

    def export_resources(self, filename):
        """Export the result to the given JSON file"""
        with open(filename, "w") as outfile:
            outfile.write(pprint.pformat(self.resources).encode('utf-8'))

    def __str__(self):
        opdesc = '{} {} {}'.format(self.service, self.region, self.operation)
        if len(self.resource_types) == 0 or self.resource_total_count == 0:
            return "{} (no resources found)".format(opdesc)
        return opdesc + ', '.join('#{}: {}'.format(key, len(listing)) for key, listing in self.resources.items())

    @classmethod
    def acquire(cls, service, region, operation):
        """Acquire the given listing by making an AWS request"""
        response = run_raw_listing_operation(service, region, operation)
        if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            raise Exception("Bad AWS HTTP Status Code", response)
        return cls(service, region, operation, response)

    @property
    def resources(self):  # pylint:disable=too-many-branches
        """Transform the response data into a dict of resource names to resource listings"""
        response = self.response.copy()
        complete = True

        del response["ResponseMetadata"]

        # Transmogrify strange cloudfront results into standard AWS format
        if self.service == "cloudfront" and self.operation in [
            "ListCloudFrontOriginAccessIdentities", "ListDistributions", "ListStreamingDistributions"
        ]:
            key = list(response.keys())[0][:-len("List")]
            response = list(response.values())[0]
            response[key] = response.get("Items", [])

        # SNS ListSubscriptions always sends a next token...
        if self.service == "sns" and self.operation == "ListSubscriptions":
            del response["NextToken"]

        if "Count" in response:
            if "MaxResults" in response:
                if response["MaxResults"] <= response["Count"]:
                    complete = False
                del response["MaxResults"]
            del response["Count"]

        if "MaxItems" in response:
            del response["MaxItems"]

        if "Quantity" in response:
            del response["Quantity"]

        for bad_thing in (
            "hasMoreResults", "IsTruncated", "Truncated", "HasMoreApplications", "HasMoreDeliveryStreams",
            "HasMoreStreams", "NextToken", "NextMarker", "Marker"
        ):
            if bad_thing in response:
                if response[bad_thing]:
                    complete = False
                del response[bad_thing]

        # Special handling for Aliases in kms, there are some reserved AWS-managed aliases.
        if self.service == "kms" and self.operation == "ListAliases":
            response["Aliases"] = [
                alias for alias in response.get("Aliases", [])
                if not alias.get("AliasName").lower().startswith("alias/aws")
            ]

        # Filter PUBLIC images from appstream
        if self.service == "appstream" and self.operation == "DescribeImages":
            response["Images"] = [
                image for image in response.get("Images", []) if not image.get("Visibility", "PRIVATE") == "PUBLIC"
            ]

        # This API returns a dict instead of a list
        if self.service == 'cloudsearch' and self.operation == 'ListDomainNames':
            response["DomainNames"] = list(response["DomainNames"].items())

        # Remove AWS supplied policies
        if self.service == "iam" and self.operation == "ListPolicies":
            response["Policies"] = [
                policy for policy in response["Policies"] if not policy['Arn'].startswith('arn:aws:iam::aws:')
            ]

        # Owner Info is not necessary
        if self.service == "s3" and self.operation == "ListBuckets":
            del response["Owner"]

        # Remove failures from ecs/DescribeClusters
        if self.service == 'ecs' and self.operation == 'DescribeClusters':
            if 'failures' in response:
                del response['failures']

        # Remove default Baseline
        if self.service == "ssm" and self.operation == "DescribePatchBaselines":
            response["BaselineIdentities"] = [
                line for line in response["BaselineIdentities"] if line['BaselineName'] != 'AWS-DefaultPatchBaseline'
            ]

        # Remove default DB Security Group
        if self.service == "rds" and self.operation == "DescribeDBSecurityGroups":
            response["DBSecurityGroups"] = [
                group for group in response["DBSecurityGroups"] if group['DBSecurityGroupName'] != 'default'
            ]

        # Filter default VPCs
        if self.service == "ec2" and self.operation == "DescribeVpcs":
            response["Vpcs"] = [vpc for vpc in response["Vpcs"] if not vpc["IsDefault"]]

        # Filter default Subnets
        if self.service == "ec2" and self.operation == "DescribeSubnets":
            response["Subnets"] = [net for net in response["Subnets"] if not net["DefaultForAz"]]

        # Filter default SGs
        if self.service == "ec2" and self.operation == "DescribeSecurityGroups":
            response["SecurityGroups"] = [sg for sg in response["SecurityGroups"] if sg["GroupName"] != "default"]

        # Filter main route tables
        if self.service == "ec2" and self.operation == "DescribeRouteTables":
            response["RouteTables"] = [
                rt for rt in response["RouteTables"] if not any(x["Main"] for x in rt["Associations"])
            ]

        # Filter default Network ACLs
        if self.service == "ec2" and self.operation == "DescribeNetworkAcls":
            response["NetworkAcls"] = [nacl for nacl in response["NetworkAcls"] if not nacl["IsDefault"]]

        for key, value in response.items():
            if not isinstance(value, list):
                raise Exception("No listing:", response)

        if not complete:
            response['truncated'] = [True]

        return response


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
                    print("    - ", pprint.pformat(item).replace("\n", "\n      "))


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


def main():
    """Parse CLI arguments to either list services, operations, queries or existing json files"""
    import argparse
    parser = argparse.ArgumentParser(
        prog="aws_list_all",
        description=(
            "List AWS resources on one account across regions and services. "
            "Saves result into json files, which can then be passed to this tool again "
            "to list the contents."
        )
    )
    subparsers = parser.add_subparsers(
        description='List of subcommands. Use <subcommand> --help for more parameters',
        dest='command',
        metavar='COMMAND'
    )
    query = subparsers.add_parser('query', description='Query AWS for resources', help='Query AWS for resources')
    query.add_argument(
        '--service', action='append', help='Restrict querying to the given service (can be specified multiple times)'
    )
    query.add_argument(
        '--region', action='append', help='Restrict querying to the given region (can be specified multiple times)'
    )
    query.add_argument(
        '--operation',
        action='append',
        help='Restrict querying to the given operation (can be specified multiple times)'
    )
    query.add_argument('--directory', default='.', help='Directory to save result listings to')
    show = subparsers.add_parser(
        'show', description='Show a summary or details of a saved listing', help='Display saved listings'
    )
    show.add_argument('listingfile', nargs='*', help='listing file(s) to load and print')
    show.add_argument('--verbose', action='store_true', help='print given listing files with detailed info')
    subparsers.add_parser(
        'list-services',
        description='Lists short names of AWS services that the current boto3 version has clients for.',
        help='List available AWS services'
    )
    ops = subparsers.add_parser(
        'list-operations',
        description='List all discovered listing operations on all services',
        help='List discovered listing operations'
    )
    ops.add_argument(
        '--service',
        action='append',
        help='Only list discovered operations of the given service (can be specified multiple times)'
    )
    args = parser.parse_args()

    if args.command == "show":
        do_list_files(args.listingfile, verbose=args.verbose)
    elif args.command == "list-services":
        for service in get_services():
            print(service)
    elif args.command == "list-operations":
        for service in args.service or get_services():
            for operation in get_listing_operations(service):
                print(service, operation)
    elif args.command == "query":
        if args.directory:
            try:
                os.makedirs(args.directory)
            except OSError:
                pass
            os.chdir(args.directory)
        services = args.service or get_services()
        do_query(services, args.region, args.operation)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
