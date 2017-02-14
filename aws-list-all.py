#!/usr/bin/env python
# pylint: disable=import-error,invalid-name
"""Module providing listing functions for all AWS services using boto3"""
from __future__ import print_function

import pickle
import pprint
import re
from random import shuffle
from multiprocessing.pool import ThreadPool

import boto3


SERVICE_BLACKLIST = [
    'cur', # costs and usage reports
    'discovery', # requires manual whitelisting
    'support', # support has no payable resources
]

DEPRECATED_OR_DISALLOWED = {
    'directconnect': ['DescribeInterconnects'], # needs opt-in
    'ec2': ['DescribeScheduledInstances', 'DescribeReservedInstancesListings'], # needs opt-in
    'emr': ['DescribeJobFlows'], # deprecated
    'iam': ['GetCredentialReport'], # credential report needs to be created
}

DISALLOWED_FOR_IAM_USERS = {
    'iam': ["ListAccessKeys", "ListMFADevices", "ListSSHPublicKeys",
            "ListServiceSpecificCredentials", "ListSigningCertificates"],
    'importexport': ["ListJobs"],
}
# DEPRECATED_OR_DISALLOWED.update(DISALLOWED_FOR_IAM_USERS)

AWS_RESOURCE_QUERIES = {
    'apigateway': ['GetSdkTypes'],
    'autoscaling': ['DescribeAdjustmentTypes', 'DescribeTerminationPolicyTypes',
                    'DescribeAutoScalingNotificationTypes', 'DescribeScalingProcessTypes',
                    'DescribeMetricCollectionTypes', 'DescribeLifecycleHookTypes'],
    'cloudhsm': ['ListAvailableZones'],
    'cloudtrail': ['ListPublicKeys'],
    'codebuild': ['ListCuratedEnvironmentImages'],
    'codedeploy': ['ListDeploymentConfigs'],
    'codepipeline': ['ListActionTypes'],
    'devicefarm': ['ListDevices', 'ListOfferings', 'ListOfferingTransactions'],
    'directconnect': ['DescribeLocations'],
    'dms': ['DescribeEndpointTypes', 'DescribeOrderableReplicationInstances'],
    'ec2': ['DescribePrefixLists', 'DescribeAvailabilityZones', 'DescribeVpcEndpointServices',
            'DescribeSpotPriceHistory', 'DescribeHostReservationOfferings', 'DescribeRegions',
            'DescribeReservedInstancesOfferings', 'DescribeIdFormat',
            'DescribeVpcClassicLinkDnsSupport'],
    'elasticache': ['DescribeCacheParameterGroups', 'DescribeCacheEngineVersions'],
    'elasticbeanstalk': ['ListAvailableSolutionStacks'],
    'elastictranscoder': ['ListPresets'],
    'elb': ['DescribeLoadBalancerPolicyTypes', 'DescribeLoadBalancerPolicies'],
    'elbv2': ['DescribeSSLPolicies'],
    'inspector': ['ListRulesPackages'],
    'lightsail': ['GetBlueprints', 'GetBundles', 'GetRegions'],
    'polly': ['DescribeVoices'],
    'rds': ['DescribeDBEngineVersions', 'DescribeSourceRegions', 'DescribeCertificates',
            'DescribeEventCategories'],
    'redshift': ['DescribeClusterVersions', 'DescribeReservedNodeOfferings',
                 'DescribeOrderableClusterOptions', 'DescribeEventCategories'],
    'route53': ['GetCheckerIpRanges', 'ListGeoLocations'],
    'ssm': ['DescribeAvailablePatches', 'GetInventorySchema'],
}

NOT_RESOURCE_DESCRIPTIONS = {
    'apigateway': ['GetAccount'],
    'autoscaling': ['DescribeAccountLimits'],
    'cloudformation': ['DescribeAccountLimits'],
    'cloudwatch': ['DescribeAlarmHistory'],
    'config': ['GetComplianceSummaryByResourceType', 'GetComplianceSummaryByConfigRule',
               'DescribeComplianceByConfigRule', 'DescribeComplianceByResource',
               'DescribeConfigRuleEvaluationStatus'],
    'devicefarm': ['GetAccountSettings', 'GetOfferingStatus'],
    'dms': ['DescribeAccountAttributes'],
    'ds': ['GetDirectoryLimits'],
    'dynamodb': ['DescribeLimits'],
    'ec2': ['DescribeAccountAttributes', 'DescribeDhcpOptions', 'DescribeVpcClassicLink',
            'DescribeVpcClassicLinkDnsSupport'],
    'ecr': ['GetAuthorizationToken'],
    'elasticache': ['DescribeReservedCacheNodesOfferings'],
    'gamelift': ['DescribeEC2InstanceLimits'],
    'iam': ['GetAccountPasswordPolicy', 'GetAccountSummary', 'GetUser'],
    'inspector': ['DescribeCrossAccountAccessRole'],
    'iot': ['GetRegistrationCode', 'DescribeEndpoint'],
    'kinesis': ['DescribeLimits'],
    'lambda': ['GetAccountSettings'],
    'opsworks': ['DescribeMyUserProfile', 'DescribeUserProfiles'],
    'opsworkscm': ['DescribeAccountAttributes'],
    'rds': ['DescribeAccountAttributes', 'DescribeDBEngineVersions',
            'DescribeReservedDBInstancesOfferings'],
    'route53': ['GetTrafficPolicyInstanceCount', 'GetHostedZoneCount', 'GetHealthCheckCount',
                'GetGeoLocation'],
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
    'cloudformation': ['GetTemplateSummary', 'DescribeStackResources', 'DescribeStackEvents',
                       'GetTemplate'],
    'cloudhsm': ['DescribeHsm', 'DescribeLunaClient'],
    'cloudtrail': ['GetEventSelectors'],
    'codecommit': ['GetBranch'],
    'cognito-idp': ['GetUser'],
    'ec2': ['DescribeSpotDatafeedSubscription'],
    'ecs': ['ListContainerInstances', 'ListServices', 'ListTasks'],
    'efs': ['DescribeMountTargets'],
    'elasticache': ['ListAllowedNodeTypeModifications', 'DescribeCacheSecurityGroups'],
    'elasticbeanstalk': ['DescribeEnvironmentManagedActionHistory', 'DescribeEnvironmentResources',
                         'DescribeEnvironmentManagedActions', 'DescribeEnvironmentHealth',
                         'DescribeInstancesHealth', 'DescribeConfigurationOptions'],
    'elbv2': ['DescribeRules', 'DescribeListeners'],
    'gamelift': ['DescribeGameSessionDetails', 'DescribeGameSessions', 'DescribePlayerSessions'],
    'health': ['DescribeEventTypes', 'DescribeEntityAggregates', 'DescribeEvents'],
    'iot': ['GetLoggingOptions'],
    'opsworks': ['DescribeAgentVersions', 'DescribeApps', 'DescribeCommands', 'DescribeDeployments',
                 'DescribeEcsClusters', 'DescribeElasticIps', 'DescribeElasticLoadBalancers',
                 'DescribeInstances', 'DescribeLayers', 'DescribePermissions', 'DescribeRaidArrays',
                 'DescribeVolumes'],
    'redshift': ['DescribeTableRestoreStatus', 'DescribeClusterSecurityGroups'],
    'route53domains': ['GetContactReachabilityStatus'],
    'shield': ['DescribeSubscription', 'ListProtections'],
    'ssm': ['DescribeAssociation'],
}

PARAMETERS = {
    'ec2': {
        'DescribeSnapshots': {'OwnerIds': ['self']},
        'DescribeImages': {'Owners': ['self']},
    },
    'iam': {
        'ListPolicies': {'Scope': 'Local'},
    },
    'ssm': {
        'ListDocuments': {'DocumentFilterList': [{'key': 'Owner', 'value': 'self'}]},
    },
}

VERBS_LISTINGS = ['Describe', 'Get', 'List']

def get_services():
    """Return a list of all service names where listable resources can be present"""
    return [service for service in boto3.Session().get_available_services()
            if not service in SERVICE_BLACKLIST]

def get_regions_for_service(service):
    """Given a service name, return a list of region names where this service can have resources"""
    if service == "s3":
        return ['us-east-1'] # s3 ListBuckets is a global request, so no region required.
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
    return set(re.sub("([A-Z])", "_\\1", x).split("_")[1]
               for x in client.meta.method_to_api_mapping.values())

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
        return opdesc + ', '.join('#{}: {}'.format(key, len(listing))
                                  for key, listing in self.resources.items())

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
                "ListCloudFrontOriginAccessIdentities",
                "ListDistributions",
                "ListStreamingDistributions"]:
            key = response.keys()[0][:-len("List")]
            response = response.values()[0]
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

        for bad_thing in ("hasMoreResults", "IsTruncated", "Truncated", "HasMoreApplications",
                          "HasMoreDeliveryStreams", "HasMoreStreams", "NextToken", "NextMarker",
                          "Marker"):
            if bad_thing in response:
                if response[bad_thing]:
                    complete = False
                del response[bad_thing]

        # Special handling for Aliases in kms, there are some reserved AWS-managed aliases.
        if self.service == "kms" and self.operation == "ListAliases":
            response["Aliases"] = [alias for alias in response.get("Aliases", [])
                                   if not alias.get("AliasName").lower().startswith("alias/aws")]
        # Filter PUBLIC images from appstream
        if self.service == "appstream" and self.operation == "DescribeImages":
            response["Images"] = [image for image in response.get("Images", [])
                                  if not image.get("Visibility", "PRIVATE") == "PUBLIC"]
        # This API returns a dict instead of a list
        if self.service == 'cloudsearch' and self.operation == 'ListDomainNames':
            response["DomainNames"] = response["DomainNames"].items()

        # Remove AWS supplied policies
        if self.service == "iam" and self.operation == "ListPolicies":
            response["Policies"] = [policy for policy in response["Policies"]
                                    if not policy['Arn'].startswith('arn:aws:iam::aws:')]

        # Owner Info is not necessary
        if self.service == "s3" and self.operation == "ListBuckets":
            del response["Owner"]

        # Remove failures from ecs/DescribeClusters
        if self.service == 'ecs' and self.operation == 'DescribeClusters':
            if 'failures' in response:
                del response['failures']

        # Remove default Baseline
        if self.service == "ssm" and self.operation == "DescribePatchBaselines":
            response["BaselineIdentities"] = [line for line in response["BaselineIdentities"]
                                              if line['BaselineName'] != 'AWS-DefaultPatchBaseline']

        # Remove default DB Security Group
        if self.service == "rds" and self.operation == "DescribeDBSecurityGroups":
            response["DBSecurityGroups"] = [group for group in response["DBSecurityGroups"]
                                            if group['DBSecurityGroupName'] != 'default']

        for key, value in response.items():
            if not isinstance(value, list):
                raise Exception("No listing:", response)

        if not complete:
            response['truncated'] = [True]

        return response


def acquire_listing(what):
    """Given a service, region and operation execute the operation, pickle and save the result and
    return a tuple of strings describing the result."""
    service, region, operation = what
    try:
        listing = Listing.acquire(service, region, operation)
        if listing.resource_total_count > 0:
            with open("{}_{}_{}.pickle".format(service, operation, region), "wb") as picklefile:
                pickle.dump(listing, picklefile)
            return ("-->", service, region, operation, ', '.join(listing.resource_types))
        else:
            return ("---", service, region, operation, ', '.join(listing.resource_types))
    except Exception as exc:  # pylint:disable=broad-except
        return ("!!!", service, region, operation, repr(exc))


def do_list_files(filenames):
    """Print out a rudimentary summary of the Listing objects contained in the given files"""
    for listing_filename in filenames:
        listing = pickle.load(open(listing_filename, "rb"))
        resources = listing.resources
        for resource_type, value in resources.items():
            print(listing.service, listing.region, listing.operation, resource_type, len(value))
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
    for result in ThreadPool(32).imap_unordered(acquire_listing, to_run):
        print(*result)


def main():
    """Parse CLI arguments to either list services, operations, queries or existing pickles"""
    import argparse
    parser = argparse.ArgumentParser(
        description="List AWS resources on one account across regions and services"
    )
    parser.add_argument('--list-services', action='store_true', help='List the services')
    parser.add_argument('--list-operations', action='store_true', help='List the operations')
    parser.add_argument('--query', action='store_true', help='Execute and query AWS')
    parser.add_argument('--service', action='append',
                        help='Restrict the given action to the given service'
                        ' (can be specified multiple times)')
    parser.add_argument('--region', action='append',
                        help='Restrict the given action to the given region '
                        '(can be specified multiple times)')
    parser.add_argument('--operation', action='append',
                        help='Restrict the given action to the given operation '
                        '(can be specified multiple times)')
    parser.add_argument('listingfile', nargs='*', help='listing file to load and print')
    args = parser.parse_args()

    services = args.service or get_services()
    if args.listingfile:
        do_list_files(args.listingfile)
    elif args.list_services:
        for service in services:
            print(service)
    elif args.list_operations:
        for service in services:
            for operation in get_listing_operations(service):
                print(service, operation)
    elif args.query:
        do_query(services, args.region, args.operation)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
