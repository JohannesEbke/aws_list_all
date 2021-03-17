import json
import pprint

import boto3

from .client import get_client

class ResourceFilter:
    def execute(self, listing, response):
        pass

class CloudfrontFilter:
    def execute(self, listing, response):
        # Transmogrify strange cloudfront results into standard AWS format
        if listing.service == 'cloudfront':
            assert len(response.keys()) == 1, 'Unexpected cloudfront response: {}'.format(response)
            key = list(response.keys())[0][:-len('List')]
            response = list(response.values())[0]
            response[key] = response.get('Items', [])
    
class MedialiveFilter:
    def execute(self, listing, response):
        # medialive List* things sends a next token; remove if no channels/lists
        if listing.service == 'medialive':
            if listing.operation == 'ListChannels' and not response['Channels']:
                if 'Channels' in response:
                    del response['Channels']
                if 'NextToken' in response:
                    del response['NextToken']
            if listing.operation == 'ListInputs' and not response['Inputs']:
                if 'Inputs' in response:
                    del response['Inputs']
                if 'NextToken' in response:
                    del response['NextToken']

class SSMListCommandsFilter:
    def execute(self, listing, response):
        # ssm ListCommands sends a next token; remove if no channels
        if listing.service == 'ssm' and listing.operation == 'ListCommands':
            if 'NextToken' in response and not response['Commands']:
                del response['NextToken']

class SNSListSubscriptionsFilter:
    def execute(self, listing, response):
        # SNS ListSubscriptions always sends a next token...
        if listing.service == 'sns' and listing.operation == 'ListSubscriptions':
            del response['NextToken']

class AthenaWorkGroupsFilter:
    def execute(self, listing, response):
        # Athena has a "primary" work group that is always present
        if listing.service == 'athena' and listing.operation == 'ListWorkGroups':
            response['WorkGroups'] = [wg for wg in response.get('WorkGroups', []) if wg['Name'] != 'primary']

class ListEventBusesFilter:
    def execute(self, listing, response):
        # Remove default event buses
        if listing.service == 'events' and listing.operation == 'ListEventBuses':
            response['EventBuses'] = [wg for wg in response.get('EventBuses', []) if wg['Name'] != 'default']

class XRayGroupsFilter:
    def execute(self, listing, response):
        # XRay has a "Default"  group that is always present
        if listing.service == 'xray' and listing.operation == 'GetGroups':
            response['Groups'] = [wg for wg in response.get('Groups', []) if wg['GroupName'] != 'Default']

class Route53ResolverFilter:
    def execute(self, listing, response):
        if listing.service == 'route53resolver':
            if listing.operation == 'ListResolverRules':
                response['ResolverRules'] = [
                    rule for rule in response.get('ResolverRules', [])
                    if rule['Id'] != 'rslvr-autodefined-rr-internet-resolver'
                ]
            if listing.operation == 'ListResolverRuleAssociations':
                response['ResolverRuleAssociations'] = [
                    rule for rule in response.get('ResolverRuleAssociations', [])
                    if rule['ResolverRuleId'] != 'rslvr-autodefined-rr-internet-resolver'
                ]

class KMSListAliasesFilter:
    def execute(self, listing, response):
        # Special handling for Aliases in kms, there are some reserved AWS-managed aliases.
        if listing.service == 'kms' and listing.operation == 'ListAliases':
            response['Aliases'] = [
                alias for alias in response.get('Aliases', [])
                if not alias.get('AliasName').lower().startswith('alias/aws')
            ]

class KMSListKeysFilter:
    def __init__(self, directory):
        self.directory = directory

    def execute(self, listing, response):
        # Special handling for service-level kms keys; derived from alias name.
        if listing.service == 'kms' and listing.operation == 'ListKeys':
            #list_aliases = run_raw_listing_operation(self.service, self.region, 'ListAliases', self.profile)
            aliases_file = '{}_{}_{}_{}.json'.format(listing.service, 'ListAliases', listing.region, listing.profile)
            aliases_file = self.directory + aliases_file
            aliases_listing = Listing.from_json(json.load(open(aliases_file, 'rb')))
            list_aliases = aliases_listing.response
            service_key_ids = [
                k.get('TargetKeyId') for k in list_aliases.get('Aliases', [])
                if k.get('AliasName').lower().startswith('alias/aws')
            ]
            response['Keys'] = [k for k in response.get('Keys', []) if k.get('KeyId') not in service_key_ids]

class AppstreamImagesFilter:
    def execute(self, listing, response):
        # Filter PUBLIC images from appstream
        if listing.service == 'appstream' and listing.operation == 'DescribeImages':
            response['Images'] = [
                image for image in response.get('Images', []) if not image.get('Visibility', 'PRIVATE') == 'PUBLIC'
            ]

class CloudsearchFilter:
    def execute(self, listing, response):
        # This API returns a dict instead of a list
        if listing.service == 'cloudsearch' and listing.operation == 'ListDomainNames':
            response['DomainNames'] = list(response['DomainNames'].items())

class CloudTrailFilter:
    def execute(self, listing, response):
        # Only list CloudTrail trails in own/Home Region
        if listing.service == 'cloudtrail' and listing.operation == 'DescribeTrails':
            response['trailList'] = [
                trail for trail in response['trailList']
                if trail.get('HomeRegion') == self.region or not trail.get('IsMultiRegionTrail')
            ]

class CloudWatchFilter:
    def execute(self, listing, response):
        # Remove AWS-default cloudwatch metrics
        if listing.service == 'cloudwatch' and listing.operation == 'ListMetrics':
            response['Metrics'] = [
                metric for metric in response['Metrics'] if not metric.get('Namespace').startswith('AWS/')
            ]

class IAMPoliciesFilter:
    def execute(self, listing, response):
        # Remove AWS supplied policies
        if listing.service == 'iam' and listing.operation == 'ListPolicies':
            response['Policies'] = [
                policy for policy in response['Policies'] if not policy['Arn'].startswith('arn:aws:iam::aws:')
            ]

class S3OwnerFilter:
    def execute(self, listing, response):
        # Owner Info is not necessary
        if listing.service == 's3' and listing.operation == 'ListBuckets':
            del response['Owner']

class ECSClustersFailureFilter:
    def execute(self, listing, response):
        # Remove failures from ecs/DescribeClusters
        if listing.service == 'ecs' and listing.operation == 'DescribeClusters':
            if 'failures' in response:
                del response['failures']

class PinpointGetAppsFilter:
    def execute(self, listing, response):
        # This API returns a dict instead of a list
        if listing.service == 'pinpoint' and listing.operation == 'GetApps':
            response['ApplicationsResponse'] = response.get('ApplicationsResponse', {}).get('Items', [])

class SSMBaselinesFilter:
    def execute(self, listing, response):
        # Remove AWS-defined Baselines
        if listing.service == 'ssm' and listing.operation == 'DescribePatchBaselines':
            response['BaselineIdentities'] = [
                line for line in response['BaselineIdentities'] if not line['BaselineName'].startswith('AWS-')
            ]

class DBSecurityGroupsFilter:
    def execute(self, listing, response):
        # Remove default DB Security Group
        if listing.service in 'rds' and listing.operation == 'DescribeDBSecurityGroups':
            response['DBSecurityGroups'] = [
                group for group in response['DBSecurityGroups'] if group['DBSecurityGroupName'] != 'default'
            ]

class DBParameterGroupsFilter:
    def execute(self, listing, response):
        # Remove default DB Parameter Groups
        if listing.service in ('rds', 'neptune', 'docdb') and listing.operation in 'DescribeDBParameterGroups':
            response['DBParameterGroups'] = [
                group for group in response['DBParameterGroups']
                if not group['DBParameterGroupName'].startswith('default.')
            ]

class DBClusterParameterGroupsFilter:
    def execute(self, listing, response):
        # Remove default DB Cluster Parameter Groups
        if listing.service in ('rds', 'neptune', 'docdb') and listing.operation in 'DescribeDBClusterParameterGroups':
            response['DBClusterParameterGroups'] = [
                group for group in response['DBClusterParameterGroups']
                if not group['DBClusterParameterGroupName'].startswith('default.')
            ]

class DBOptionGroupsFilter:
    def execute(self, listing, response):
        # Remove default DB Option Groups
        if listing.service == 'rds' and listing.operation == 'DescribeOptionGroups':
            response['OptionGroupsList'] = [
                group for group in response['OptionGroupsList'] if not group['OptionGroupName'].startswith('default:')
            ]

class EC2VPCFilter:
    def execute(self, listing, response):
        # Filter default VPCs
        if listing.service == 'ec2' and listing.operation == 'DescribeVpcs':
            response['Vpcs'] = [vpc for vpc in response['Vpcs'] if not vpc['IsDefault']]

class EC2SubnetsFilter:
    def execute(self, listing, response):
        # Filter default Subnets
        if listing.service == 'ec2' and listing.operation == 'DescribeSubnets':
            response['Subnets'] = [net for net in response['Subnets'] if not net['DefaultForAz']]

class EC2SecurityGroupsFilter:
    def execute(self, listing, response):
        # Filter default SGs
        if listing.service == 'ec2' and listing.operation == 'DescribeSecurityGroups':
            response['SecurityGroups'] = [sg for sg in response['SecurityGroups'] if sg['GroupName'] != 'default']

class EC2RouteTablesFilter:
    def execute(self, listing, response):
        # Filter main route tables
        if listing.service == 'ec2' and listing.operation == 'DescribeRouteTables':
            response['RouteTables'] = [
                rt for rt in response['RouteTables'] if not any(x['Main'] for x in rt['Associations'])
            ]

class EC2NetworkAclsFilter:
    def execute(self, listing, response):
        # Filter default Network ACLs
        if listing.service == 'ec2' and listing.operation == 'DescribeNetworkAcls':
            response['NetworkAcls'] = [nacl for nacl in response['NetworkAcls'] if not nacl['IsDefault']]

class EC2InternetGatewaysFilter:
    def __init__(self, directory):
        self.directory = directory

    def execute(self, listing, response):
        # Filter default Internet Gateways
        if listing.service == 'ec2' and listing.operation == 'DescribeInternetGateways':
            #describe_vpcs = run_raw_listing_operation(self.service, self.region, 'DescribeVpcs', self.profile)
            vpcs_file = '{}_{}_{}_{}.json'.format(listing.service, 'DescribeVpcs', listing.region, listing.profile)
            vpcs_file = self.directory + vpcs_file
            vpcs_listing = Listing.from_json(json.load(open(vpcs_file, 'rb')))
            describe_vpcs = vpcs_listing.response
            vpcs = {v['VpcId']: v for v in describe_vpcs.get('Vpcs', [])}
            internet_gateways = []
            # print(self.response)
            # print(response)
            for ig in response['InternetGateways']:
                attachments = ig.get('Attachments', [])
                # more than one, it cannot be default.
                if len(attachments) != 1:
                    continue
                vpc = attachments[0].get('VpcId')
                if not vpcs.get(vpc, {}).get('IsDefault', False):
                    internet_gateways.append(ig)
            response['InternetGateways'] = internet_gateways

class EC2FpgaImagesFilter:
    def execute(self, listing, response):
        # Filter Public images from ec2.fpga images
        if listing.service == 'ec2' and listing.operation == 'DescribeFpgaImages':
            response['FpgaImages'] = [image for image in response.get('FpgaImages', []) if not image.get('Public')]

class WorkmailDeletedOrganizationsFilter:
    def execute(self, listing, response):
        # Remove deleted Organizations
        if listing.service == 'workmail' and listing.operation == 'ListOrganizations':
            response['OrganizationSummaries'] = [
                s for s in response.get('OrganizationSummaries', []) if not s.get('State') == 'Deleted'
            ]

class ElasticacheSubnetGroupsFilter:
    def execute(self, listing, response):
        if listing.service == 'elasticache' and listing.operation == 'DescribeCacheSubnetGroups':
            response['CacheSubnetGroups'] = [
                g for g in response.get('CacheSubnetGroups', []) if g.get('CacheSubnetGroupName') != 'default'
            ]