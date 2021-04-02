import json
import pprint

import boto3
import json
from datetime import datetime

from .apply_filter import apply_filters
from .client import get_client
from .resource_filter import *

RESULT_TYPE_LENGTH = 3

PARAMETERS = {
    'cloudfront': {
        'ListCachePolicies': {
            'Type': 'custom'
        },
    },
    'ec2': {
        'DescribeSnapshots': {
            'OwnerIds': ['self']
        },
        'DescribeImages': {
            'Owners': ['self']
        },
    },
    'ecs': {
        'ListTaskDefinitionFamilies': {
            'status': 'ACTIVE',
        }
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
    'emr': {
        'ListClusters': {
            'ClusterStates': ['STARTING', 'BOOTSTRAPPING', 'RUNNING', 'WAITING', 'TERMINATING'],
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
    'waf-regional': {
        'ListLoggingConfigurations': {
            'Limit': 100,
        },
    },
}

ssf = list(
    boto3.Session(
        region_name='us-east-1'
    ).client('cloudformation').meta.service_model.shape_for('ListStacksInput').members['StackStatusFilter'].member.enum
)
ssf.remove('DELETE_COMPLETE')
PARAMETERS.setdefault('cloudformation', {})['ListStacks'] = {'StackStatusFilter': ssf}


def run_raw_listing_operation(service, region, operation, profile):
    """Execute a given operation and return its raw result"""
    client = get_client(service, region, profile)
    api_to_method_mapping = dict((v, k) for k, v in client.meta.method_to_api_mapping.items())
    parameters = PARAMETERS.get(service, {}).get(operation, {})
    op_model = client.meta.service_model.operation_model(operation)
    required_members = op_model.input_shape.required_members if op_model.input_shape else []
    if "MaxResults" in required_members:
        # Current limit for cognito identity pools is 60
        parameters["MaxResults"] = 10
    return getattr(client, api_to_method_mapping[operation])(**parameters)


class FilteredListing(object):

    def __init__(self, input, directory='./', unfilter=None):
        self.input = input
        self.directory = directory
        self.unfilter = [] if unfilter is None else unfilter

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
        with open(filename, 'w') as outfile:
            outfile.write(pprint.pformat(self.resources).encode('utf-8'))

    def __str__(self):
        opdesc = '{} {} {} {}'.format(self.input.service, self.input.region, self.input.operation, self.input.profile)
        if len(self.resource_types) == 0 or self.resource_total_count == 0:
            return '{} (no resources found)'.format(opdesc)
        return opdesc + ', '.join('#{}: {}'.format(key, len(listing)) for key, listing in self.resources.items())

    @property
    def resources(self):
        """Transform the response data into a dict of resource names to resource listings"""
        if not(self.input.response):
            return self.input.response.copy()
        response = self.input.response.copy()
        complete = True
        del response['ResponseMetadata']

        complete = apply_filters(self.input, self.unfilter, response, complete)
        unfilterList = self.unfilter

        # Following two if-blocks rely on certain JSON-files being present, hence the DEPENDENT_OPERATIONS
        # in query.py. May need rework to function without dependencies.
        
        # Special handling for service-level kms keys; derived from alias name.
        if 'kmsListKeys' not in unfilterList and self.input.service == 'kms' and self.input.operation == 'ListKeys':
            try:
                aliases_file = '{}_{}_{}_{}.json'.format(self.input.service, 'ListAliases', self.input.region, self.input.profile)
                aliases_file = self.directory + '/' + aliases_file
                aliases_listing = RawListing.from_json(json.load(open(aliases_file, 'rb')))
                list_aliases = aliases_listing.response
                service_key_ids = [
                    k.get('TargetKeyId') for k in list_aliases.get('Aliases', [])
                    if k.get('AliasName').lower().startswith('alias/aws')
                ]
                response['Keys'] = [k for k in response.get('Keys', []) if k.get('KeyId') not in service_key_ids]
            except Exception as exc:
                self.input.error = repr(exc)

        # Filter default Internet Gateways
        if 'ec2InternetGateways' not in unfilterList and self.input.service == 'ec2' and self.input.operation == 'DescribeInternetGateways':
            try:
                vpcs_file = '{}_{}_{}_{}.json'.format(self.input.service, 'DescribeVpcs', self.input.region, self.input.profile)
                vpcs_file = self.directory + '/' + vpcs_file
                vpcs_listing = RawListing.from_json(json.load(open(vpcs_file, 'rb')))
                describe_vpcs = vpcs_listing.response
                vpcs = {v['VpcId']: v for v in describe_vpcs.get('Vpcs', [])}
                internet_gateways = []
                for ig in response['InternetGateways']:
                    attachments = ig.get('Attachments', [])
                    # more than one, it cannot be default.
                    if len(attachments) != 1:
                        continue
                    vpc = attachments[0].get('VpcId')
                    if not vpcs.get(vpc, {}).get('IsDefault', False):
                        internet_gateways.append(ig)
                response['InternetGateways'] = internet_gateways
            except Exception as exc:
                self.input.error = repr(exc)

        for key, value in response.items():
            if not isinstance(value, list):
                raise Exception('No listing: {} is no list:'.format(key), response)

        if not complete:
            response['truncated'] = [True]

        # Update JSON-file in case an error occurred during resources-processing
        if len(self.input.error) > RESULT_TYPE_LENGTH:
            self.input.error = '!!!'
            with open('{}_{}_{}_{}.json'.format(
                self.input.service, self.input.operation, self.input.region, self.input.profile), 'w') as jsonfile:
                json.dump(self.input.to_json(), jsonfile, default=datetime.isoformat)

        return response


class RawListing(object):
    """Represents a listing operation on an AWS service and its result"""
    def __init__(self, service, region, operation, response, profile, error=''):
        self.service = service
        self.region = region
        self.operation = operation
        self.response = response
        self.profile = profile
        self.error = error

    def to_json(self):
        return {
            'service': self.service,
            'region': self.region,
            'profile': self.profile,
            'operation': self.operation,
            'response': self.response,
            'error': self.error,
        }

    @classmethod
    def from_json(cls, data):
        return cls(
            service=data.get('service'),
            region=data.get('region'),
            profile=data.get('profile'),
            operation=data.get('operation'),
            response=data.get('response'),
            error=data.get('error')
        )

    def __str__(self):
        opdesc = '{} {} {} {}'.format(self.service, self.region, self.operation, self.profile)
        if len(self.resource_types) == 0 or self.resource_total_count == 0:
            return '{} (no resources found)'.format(opdesc)
        return opdesc + ', '.join('#{}: {}'.format(key, len(listing)) for key, listing in self.resources.items())

    @classmethod
    def acquire(cls, service, region, operation, profile):
        """Acquire the given listing by making an AWS request"""
        response = run_raw_listing_operation(service, region, operation, profile)
        # if response['ResponseMetadata']['HTTPStatusCode'] != 200:
        #     raise Exception('Bad AWS HTTP Status Code', response)
        return cls(service, region, operation, response, profile)

    @property
    def resources(self):  # pylint:disable=too-many-branches
        """Transform the response data into a dict of resource names to resource listings"""
        if not(self.response):
            return self.response.copy()
        response = self.response.copy()
        complete = True

        del response['ResponseMetadata']
        #complete = apply_filters(self, response, complete)

        for key, value in response.items():
            if not isinstance(value, list):
                raise Exception('No listing: {} is no list:'.format(key), response)

        if not complete:
            response['truncated'] = [True]

        return response


class ResultListing(object):
    """Represents a listing result summary acquired from the function acquire_listing"""
    def __init__(self, input, result_type, details):
        self.input = input
        self.result_type = result_type
        self.details = details

    @property
    def to_tuple(self):
        """Return a tiple of strings describing the result of an executed query"""
        return (self.result_type, self.input.service, self.input.region, 
            self.input.operation, self.input.profile, self.details)
