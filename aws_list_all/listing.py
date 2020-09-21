import pprint

import boto3

from .client import get_client

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


class Listing(object):
    """Represents a listing operation on an AWS service and its result"""
    def __init__(self, service, region, operation, response, profile):
        self.service = service
        self.region = region
        self.operation = operation
        self.response = response
        self.profile = profile

    def to_json(self):
        return {
            'service': self.service,
            'region': self.region,
            'profile': self.profile,
            'operation': self.operation,
            'response': self.response,
        }

    @classmethod
    def from_json(cls, data):
        return cls(
            service=data.get('service'),
            region=data.get('region'),
            profile=data.get('profile'),
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
        with open(filename, 'w') as outfile:
            outfile.write(pprint.pformat(self.resources).encode('utf-8'))

    def __str__(self):
        opdesc = '{} {} {} {}'.format(self.service, self.region, self.operation, self.profile)
        if len(self.resource_types) == 0 or self.resource_total_count == 0:
            return '{} (no resources found)'.format(opdesc)
        return opdesc + ', '.join('#{}: {}'.format(key, len(listing)) for key, listing in self.resources.items())

    @classmethod
    def acquire(cls, service, region, operation, profile):
        """Acquire the given listing by making an AWS request"""
        response = run_raw_listing_operation(service, region, operation, profile)
        if response['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise Exception('Bad AWS HTTP Status Code', response)
        return cls(service, region, operation, response, profile)

    @property
    def resources(self):  # pylint:disable=too-many-branches
        """Transform the response data into a dict of resource names to resource listings"""
        response = self.response.copy()
        complete = True

        del response['ResponseMetadata']

        # Transmogrify strange cloudfront results into standard AWS format
        if self.service == 'cloudfront':
            assert len(response.keys()) == 1, 'Unexpected cloudfront response: {}'.format(response)
            key = list(response.keys())[0][:-len('List')]
            response = list(response.values())[0]
            response[key] = response.get('Items', [])

        # medialive List* things sends a next token; remove if no channels/lists
        if self.service == 'medialive':
            if self.operation == 'ListChannels' and not response['Channels']:
                if 'Channels' in response:
                    del response['Channels']
                if 'NextToken' in response:
                    del response['NextToken']
            if self.operation == 'ListInputs' and not response['Inputs']:
                if 'Inputs' in response:
                    del response['Inputs']
                if 'NextToken' in response:
                    del response['NextToken']

        # ssm ListCommands sends a next token; remove if no channels
        if self.service == 'ssm' and self.operation == 'ListCommands':
            if 'NextToken' in response and not response['Commands']:
                del response['NextToken']

        # SNS ListSubscriptions always sends a next token...
        if self.service == 'sns' and self.operation == 'ListSubscriptions':
            del response['NextToken']

        # Athena has a "primary" work group that is always present
        if self.service == 'athena' and self.operation == 'ListWorkGroups':
            response['WorkGroups'] = [wg for wg in response.get('WorkGroups', []) if wg['Name'] != 'primary']

        # Remove default event buses
        if self.service == 'events' and self.operation == 'ListEventBuses':
            response['EventBuses'] = [wg for wg in response.get('EventBuses', []) if wg['Name'] != 'default']

        # XRay has a "Default"  group that is always present
        if self.service == 'xray' and self.operation == 'GetGroups':
            response['Groups'] = [wg for wg in response.get('Groups', []) if wg['GroupName'] != 'Default']

        if self.service == 'route53resolver':
            if self.operation == 'ListResolverRules':
                response['ResolverRules'] = [
                    rule for rule in response.get('ResolverRules', [])
                    if rule['Id'] != 'rslvr-autodefined-rr-internet-resolver'
                ]
            if self.operation == 'ListResolverRuleAssociations':
                response['ResolverRuleAssociations'] = [
                    rule for rule in response.get('ResolverRuleAssociations', [])
                    if rule['ResolverRuleId'] != 'rslvr-autodefined-rr-internet-resolver'
                ]

        if 'Count' in response:
            if 'MaxResults' in response:
                if response['MaxResults'] <= response['Count']:
                    complete = False
                del response['MaxResults']
            del response['Count']

        if 'Quantity' in response:
            if 'MaxItems' in response:
                if response['MaxItems'] <= response['Quantity']:
                    complete = False
                del response['MaxItems']
            del response['Quantity']

        for neutral_thing in ('MaxItems', 'MaxResults', 'Quantity'):
            if neutral_thing in response:
                del response[neutral_thing]

        for bad_thing in (
            'hasMoreResults', 'IsTruncated', 'Truncated', 'HasMoreApplications', 'HasMoreDeliveryStreams',
            'HasMoreStreams', 'NextToken', 'NextMarker', 'nextMarker', 'Marker'
        ):
            if bad_thing in response:
                if response[bad_thing]:
                    complete = False
                del response[bad_thing]

        # Special handling for Aliases in kms, there are some reserved AWS-managed aliases.
        if self.service == 'kms' and self.operation == 'ListAliases':
            response['Aliases'] = [
                alias for alias in response.get('Aliases', [])
                if not alias.get('AliasName').lower().startswith('alias/aws')
            ]

        # Special handling for service-level kms keys; derived from alias name.
        if self.service == 'kms' and self.operation == 'ListKeys':
            list_aliases = run_raw_listing_operation(self.service, self.region, 'ListAliases', self.profile)
            service_key_ids = [
                k.get('TargetKeyId') for k in list_aliases.get('Aliases', [])
                if k.get('AliasName').lower().startswith('alias/aws')
            ]
            response['Keys'] = [k for k in response.get('Keys', []) if k.get('KeyId') not in service_key_ids]

        # Filter PUBLIC images from appstream
        if self.service == 'appstream' and self.operation == 'DescribeImages':
            response['Images'] = [
                image for image in response.get('Images', []) if not image.get('Visibility', 'PRIVATE') == 'PUBLIC'
            ]

        # This API returns a dict instead of a list
        if self.service == 'cloudsearch' and self.operation == 'ListDomainNames':
            response['DomainNames'] = list(response['DomainNames'].items())

        # Only list CloudTrail trails in own/Home Region
        if self.service == 'cloudtrail' and self.operation == 'DescribeTrails':
            response['trailList'] = [
                trail for trail in response['trailList']
                if trail.get('HomeRegion') == self.region or not trail.get('IsMultiRegionTrail')
            ]

        # Remove AWS-default cloudwatch metrics
        if self.service == 'cloudwatch' and self.operation == 'ListMetrics':
            response['Metrics'] = [
                metric for metric in response['Metrics'] if not metric.get('Namespace').startswith('AWS/')
            ]

        # Remove AWS supplied policies
        if self.service == 'iam' and self.operation == 'ListPolicies':
            response['Policies'] = [
                policy for policy in response['Policies'] if not policy['Arn'].startswith('arn:aws:iam::aws:')
            ]

        # Owner Info is not necessary
        if self.service == 's3' and self.operation == 'ListBuckets':
            del response['Owner']

        # Remove failures from ecs/DescribeClusters
        if self.service == 'ecs' and self.operation == 'DescribeClusters':
            if 'failures' in response:
                del response['failures']

        # This API returns a dict instead of a list
        if self.service == 'pinpoint' and self.operation == 'GetApps':
            response['ApplicationsResponse'] = response.get('ApplicationsResponse', {}).get('Items', [])

        # Remove AWS-defined Baselines
        if self.service == 'ssm' and self.operation == 'DescribePatchBaselines':
            response['BaselineIdentities'] = [
                line for line in response['BaselineIdentities'] if not line['BaselineName'].startswith('AWS-')
            ]

        # Remove default DB Security Group
        if self.service in 'rds' and self.operation == 'DescribeDBSecurityGroups':
            response['DBSecurityGroups'] = [
                group for group in response['DBSecurityGroups'] if group['DBSecurityGroupName'] != 'default'
            ]

        # Remove default DB Parameter Groups
        if self.service in ('rds', 'neptune', 'docdb') and self.operation in 'DescribeDBParameterGroups':
            response['DBParameterGroups'] = [
                group for group in response['DBParameterGroups']
                if not group['DBParameterGroupName'].startswith('default.')
            ]

        # Remove default DB Cluster Parameter Groups
        if self.service in ('rds', 'neptune', 'docdb') and self.operation in 'DescribeDBClusterParameterGroups':
            response['DBClusterParameterGroups'] = [
                group for group in response['DBClusterParameterGroups']
                if not group['DBClusterParameterGroupName'].startswith('default.')
            ]

        # Remove default DB Option Groups
        if self.service == 'rds' and self.operation == 'DescribeOptionGroups':
            response['OptionGroupsList'] = [
                group for group in response['OptionGroupsList'] if not group['OptionGroupName'].startswith('default:')
            ]

        # Filter default VPCs
        if self.service == 'ec2' and self.operation == 'DescribeVpcs':
            response['Vpcs'] = [vpc for vpc in response['Vpcs'] if not vpc['IsDefault']]

        # Filter default Subnets
        if self.service == 'ec2' and self.operation == 'DescribeSubnets':
            response['Subnets'] = [net for net in response['Subnets'] if not net['DefaultForAz']]

        # Filter default SGs
        if self.service == 'ec2' and self.operation == 'DescribeSecurityGroups':
            response['SecurityGroups'] = [sg for sg in response['SecurityGroups'] if sg['GroupName'] != 'default']

        # Filter main route tables
        if self.service == 'ec2' and self.operation == 'DescribeRouteTables':
            response['RouteTables'] = [
                rt for rt in response['RouteTables'] if not any(x['Main'] for x in rt['Associations'])
            ]

        # Filter default Network ACLs
        if self.service == 'ec2' and self.operation == 'DescribeNetworkAcls':
            response['NetworkAcls'] = [nacl for nacl in response['NetworkAcls'] if not nacl['IsDefault']]

        # Filter default Internet Gateways
        if self.service == 'ec2' and self.operation == 'DescribeInternetGateways':
            describe_vpcs = run_raw_listing_operation(self.service, self.region, 'DescribeVpcs', self.profile)
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

        # Filter Public images from ec2.fpga images
        if self.service == 'ec2' and self.operation == 'DescribeFpgaImages':
            response['FpgaImages'] = [image for image in response.get('FpgaImages', []) if not image.get('Public')]

        # Remove deleted Organizations
        if self.service == 'workmail' and self.operation == 'ListOrganizations':
            response['OrganizationSummaries'] = [
                s for s in response.get('OrganizationSummaries', []) if not s.get('State') == 'Deleted'
            ]

        if self.service == 'elasticache' and self.operation == 'DescribeCacheSubnetGroups':
            response['CacheSubnetGroups'] = [
                g for g in response.get('CacheSubnetGroups', []) if g.get('CacheSubnetGroupName') != 'default'
            ]

        # interpret nextToken in several services
        if (self.service, self.operation) in (('inspector', 'ListFindings'), ('logs', 'DescribeLogGroups')):
            if response.get('nextToken'):
                complete = False
                del response['nextToken']

        for key, value in response.items():
            if not isinstance(value, list):
                raise Exception('No listing: {} is no list:'.format(key), response)

        if not complete:
            response['truncated'] = [True]

        return response
