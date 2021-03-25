import json
import os
import sys

from .fixing_filter import *
from .resource_filter import *

def apply_filters(listing, unfilterList, response, complete):
    """Apply filters for operations to be handled in a special way or 
        to remove default resources from the response"""
    apply_complete = complete

    if not('cloudfront' in unfilterList):
        filter = CloudfrontFilter()
        filter.execute(listing, response)

    if not('medialive' in unfilterList):
        filter = MedialiveFilter()
        filter.execute(listing, response)

    if not('ssmListCommands' in unfilterList):
        filter = SSMListCommandsFilter()
        filter.execute(listing, response)

    if not('snsListSubscriptions' in unfilterList):
        filter = SNSListSubscriptionsFilter()
        filter.execute(listing, response)

    if not('athenaWorkGroups' in unfilterList):
        filter = AthenaWorkGroupsFilter()
        filter.execute(listing, response)

    if not('listEventBuses' in unfilterList):
        filter = ListEventBusesFilter()
        filter.execute(listing, response)

    if not('xRayGroups' in unfilterList):
        filter = XRayGroupsFilter()
        filter.execute(listing, response)

    if not('route53Resolver' in unfilterList):
        filter = Route53ResolverFilter()
        filter.execute(listing, response)

    filter = CountFilter(apply_complete)
    filter.execute(listing, response)
    apply_complete = filter.complete

    filter = QuantityFilter(apply_complete)
    filter.execute(listing, response)
    apply_complete = filter.complete

    filter = NeutralThingFilter()
    filter.execute(listing, response)

    filter = BadThingFilter(apply_complete)
    filter.execute(listing, response)
    apply_complete = filter.complete

    if not('kmsListAliases' in unfilterList):
        filter = KMSListAliasesFilter()
        filter.execute(listing, response)

    if not('appstreamImages' in unfilterList):
        filter = AppstreamImagesFilter()
        filter.execute(listing, response)

    if not('cloudsearch' in unfilterList):
        filter = CloudsearchFilter()
        filter.execute(listing, response)

    if not('cloudTrail' in unfilterList):
        filter = CloudTrailFilter()
        filter.execute(listing, response)

    if not('cloudWatch' in unfilterList):
        filter = CloudWatchFilter()
        filter.execute(listing, response)

    if not('iamPolicies' in unfilterList):
        filter = IAMPoliciesFilter()
        filter.execute(listing, response)

    if not('s3Owner' in unfilterList):
        filter = S3OwnerFilter()
        filter.execute(listing, response)

    if not('ecsClustersFailure' in unfilterList):
        filter = ECSClustersFailureFilter()
        filter.execute(listing, response)

    if not('pinpointGetApps' in unfilterList):
        filter = PinpointGetAppsFilter()
        filter.execute(listing, response)

    if not('ssmBaselines' in unfilterList):
        filter = SSMBaselinesFilter()
        filter.execute(listing, response)

    if not('dbSecurityGroups' in unfilterList):
        filter = DBSecurityGroupsFilter()
        filter.execute(listing, response)

    if not('dbParameterGroups' in unfilterList):
        filter = DBParameterGroupsFilter()
        filter.execute(listing, response)

    if not('dbClusterParameterGroups' in unfilterList):
        filter = DBClusterParameterGroupsFilter()
        filter.execute(listing, response)

    if not('dbOptionGroups' in unfilterList):
        filter = DBOptionGroupsFilter()
        filter.execute(listing, response)

    if not('ec2VPC' in unfilterList):
        filter = EC2VPCFilter()
        filter.execute(listing, response)

    if not('ec2Subnets' in unfilterList):
        filter = EC2SubnetsFilter()
        filter.execute(listing, response)

    if not('ec2SecurityGroups' in unfilterList):
        filter = EC2SecurityGroupsFilter()
        filter.execute(listing, response)

    if not('ec2RouteTables' in unfilterList):
        filter = EC2RouteTablesFilter()
        filter.execute(listing, response)

    if not('ec2NetworkAcls' in unfilterList):
        filter = EC2NetworkAclsFilter()
        filter.execute(listing, response) 

    if not('ec2FpgaImages' in unfilterList):
        filter = EC2FpgaImagesFilter()
        filter.execute(listing, response) 

    if not('workmailDeletedOrganizations' in unfilterList):
        filter = WorkmailDeletedOrganizationsFilter()
        filter.execute(listing, response) 

    if not('elasticacheSubnetGroups' in unfilterList):
        filter = ElasticacheSubnetGroupsFilter()
        filter.execute(listing, response)    

    filter = NextTokenFilter(apply_complete)
    filter.execute(listing, response)
    apply_complete = filter.complete

    return apply_complete




