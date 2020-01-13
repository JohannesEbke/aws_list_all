from __future__ import print_function

import re
from collections import defaultdict
from json import load, dump
from multiprocessing.pool import ThreadPool
from socket import gethostbyname

import boto3
from pkg_resources import resource_stream, resource_filename

from app_json_file_cache import AppCache

from .client import get_client

cache = AppCache('aws_list_all')

VERBS_LISTINGS = ['Describe', 'Get', 'List']

SERVICE_BLACKLIST = [
    'alexaforbusiness',  # TODO: Mostly organization-specific calls and would need to be queried differently
    'apigatewaymanagementapi',  # This API allows management of deployed APIs, and requires an endpoint per API.
    'cloudsearchdomain',  # Domain-specific endpoint required
    'kinesis-video-archived-media',  # API operating on stream-specific endpoints
    'kinesis-video-media',  # API operating on stream-specific endpoints
    'managedblockchain',  # TODO: Unclear, does not have a region
    'mediastore-data',  # Mediastore Container-specific endpoint required
    's3control',  # TODO: Account-ID specific endpoint required
]

DEPRECATED_OR_DISALLOWED = {
    # # service need opt-in
    # 'alexaforbusiness': [
    # 'GetDevice',
    # 'GetProfile',
    # 'GetRoom',
    # 'GetSkillGroup',
    # 'ListSkills',
    # ],
    'config': [
        'DescribeAggregationAuthorizations',
        'DescribeConfigurationAggregators',
        'DescribePendingAggregationRequests',
    ],
    # service need opt-in
    # 'cloudhsm': [
    # 'ListHapgs',
    # 'ListHsms',
    # 'ListLunaClients',
    # ],
    # 'directconnect': ['DescribeInterconnects'],  # needs opt-in
    'dms': [
        # migration service needs to be created
        'DescribeReplicationTaskAssessmentResults'
    ],
    # 'ec2': ['DescribeScheduledInstances', 'DescribeReservedInstancesListings'],  # needs opt-in
    'emr': ['DescribeJobFlows'],  # deprecated
    'greengrass': ['GetServiceRoleForAccount'],  # Role needs to be created
    'iam': ['GetCredentialReport'],  # credential report needs to be created
    'iot': ['DescribeDefaultAuthorizer'],  # authorizer needs to be created
    'mediaconvert': ['ListJobTemplates', 'ListJobs', 'ListPresets',
                     'ListQueues'],  # service needs customer-specific endpoint
    # 'mturk': [
    # 'GetAccountBalance', 'ListBonusPayments', 'ListHITs', 'ListQualificationRequests', 'ListReviewableHITs',
    # 'ListWorkerBlocks'
    # ],  # service needs opt-in
    'servicecatalog': ['ListTagOptions'],  # requires a Tag Option Migration
    'workdocs': ['DescribeUsers'],  # need to be AWS-root
}

DISALLOWED_FOR_IAM_USERS = {
    'iam': [
        'ListAccessKeys', 'ListMFADevices', 'ListSSHPublicKeys', 'ListServiceSpecificCredentials',
        'ListSigningCertificates'
    ],
    'importexport': ['ListJobs'],
}
# DEPRECATED_OR_DISALLOWED.update(DISALLOWED_FOR_IAM_USERS)

AWS_RESOURCE_QUERIES = {
    'apigateway': ['GetSdkTypes'],
    'autoscaling': [
        'DescribeAdjustmentTypes', 'DescribeTerminationPolicyTypes', 'DescribeAutoScalingNotificationTypes',
        'DescribeScalingProcessTypes', 'DescribeMetricCollectionTypes', 'DescribeLifecycleHookTypes'
    ],
    'backup': ['GetSupportedResourceTypes', 'ListBackupPlanTemplates'],
    'clouddirectory': ['ListManagedSchemaArns'],
    'cloudhsm': ['ListAvailableZones'],
    'cloudtrail': ['ListPublicKeys'],
    'codebuild': ['ListCuratedEnvironmentImages'],
    'codedeploy': ['ListDeploymentConfigs'],
    'codepipeline': ['ListActionTypes'],
    'devicefarm': ['ListDevices', 'ListOfferings', 'ListOfferingTransactions'],
    'directconnect': ['DescribeLocations'],
    'dynamodb': ['DescribeEndpoints'],
    'dms': ['DescribeEndpointTypes', 'DescribeOrderableReplicationInstances', 'DescribeEventCategories'],
    'docdb': ['DescribeDBEngineVersions', 'DescribeEventCategories'],
    'ec2': [
        'DescribePrefixLists', 'DescribeAvailabilityZones', 'DescribeVpcEndpointServices', 'DescribeSpotPriceHistory',
        'DescribeHostReservationOfferings', 'DescribeRegions', 'DescribeReservedInstancesOfferings', 'DescribeIdFormat',
        'DescribeVpcClassicLinkDnsSupport', 'DescribeAggregateIdFormat'
    ],
    'elasticache': ['DescribeCacheParameterGroups', 'DescribeCacheEngineVersions', 'DescribeServiceUpdates'],
    'elasticbeanstalk': ['ListAvailableSolutionStacks', 'PlatformSummaryList'],
    'elastictranscoder': ['ListPresets'],
    'elb': ['DescribeLoadBalancerPolicyTypes', 'DescribeLoadBalancerPolicies'],
    'elbv2': ['DescribeSSLPolicies'],
    'es': ['DescribeReservedElasticsearchInstanceOfferings', 'GetCompatibleElasticsearchVersions'],
    'groundstation': ['ListGroundStations'],
    'inspector': ['ListRulesPackages'],
    'lex-models': ['GetBuiltinIntents', 'GetBuiltinSlotTypes'],
    'lightsail': [
        'GetBlueprints', 'GetBundles', 'GetRegions', 'GetRelationalDatabaseBlueprints', 'GetRelationalDatabaseBundles'
    ],
    'mediaconvert': ['DescribeEndpoints'],
    'medialive': ['ListOfferings'],
    'mobile': ['ListBundles'],
    'mq': ['DescribeBrokerInstanceOptions', 'DescribeBrokerEngineTypes'],
    'neptune': ['DescribeDBEngineVersions', 'DescribeEventCategories'],
    'personalize': ['ListRecipes'],
    'pricing': ['DescribeServices'],
    'polly': ['DescribeVoices'],
    'rds': ['DescribeDBEngineVersions', 'DescribeSourceRegions', 'DescribeCertificates', 'DescribeEventCategories'],
    'redshift': [
        'DescribeClusterVersions',
        'DescribeReservedNodeOfferings',
        'DescribeOrderableClusterOptions',
        'DescribeEventCategories',
        'DescribeClusterTracks',
    ],
    'route53': ['GetCheckerIpRanges', 'ListGeoLocations'],
    'service-quotas': ['ListServices'],
    'signer': ['ListSigningPlatforms'],
    'ssm': ['DescribeAvailablePatches', 'GetInventorySchema'],
    'xray': ['GetSamplingRules'],
}

NOT_RESOURCE_DESCRIPTIONS = {
    'apigateway': ['GetAccount'],
    'autoscaling': ['DescribeAccountLimits'],
    'alexaforbusiness': ['GetInvitationConfiguration'],
    'athena': ['ListQueryExecutions'],
    'chime': ['GetGlobalSettings'],
    'cloudformation': ['DescribeAccountLimits'],
    'cloudwatch': ['DescribeAlarmHistory'],
    'codebuild': ['ListBuilds'],
    'config': [
        'GetComplianceSummaryByResourceType', 'GetComplianceSummaryByConfigRule', 'DescribeComplianceByConfigRule',
        'DescribeComplianceByResource', 'DescribeConfigRuleEvaluationStatus', 'GetDiscoveredResourceCounts'
    ],
    'dax': ['DescribeDefaultParameters', 'DescribeParameterGroups'],
    'devicefarm': ['GetAccountSettings', 'GetOfferingStatus'],
    'discovery': ['GetDiscoverySummary'],
    'dms': ['DescribeAccountAttributes', 'DescribeEventCategories'],
    'docdb': ['DescribeEvents'],
    'ds': ['GetDirectoryLimits'],
    'dynamodb': ['DescribeLimits'],
    'ec2': [
        'DescribeAccountAttributes', 'DescribeDhcpOptions', 'DescribeVpcClassicLink',
        'DescribeVpcClassicLinkDnsSupport', 'DescribePrincipalIdFormat', 'GetEbsDefaultKmsKeyId',
        'GetEbsEncryptionByDefault'
    ],
    'ecr': ['GetAuthorizationToken'],
    'ecs': ['DescribeClusters'],  # This gives duplicates from ListClusters, and also includes deleted clusters
    'elasticache': ['DescribeReservedCacheNodesOfferings'],
    'elasticbeanstalk': ['DescribeAccountAttributes', 'DescribeEvents'],
    'elb': ['DescribeAccountLimits'],
    'elbv2': ['DescribeAccountLimits'],
    'es': ['ListElasticsearchVersions'],
    'events': ['DescribeEventBus'],
    'fms': ['GetAdminAccount', 'GetNotificationChannel'],
    'gamelift': ['DescribeEC2InstanceLimits', 'DescribeMatchmakingConfigurations', 'DescribeMatchmakingRuleSets'],
    'glue': ['GetCatalogImportStatus', 'GetDataCatalogEncryptionSettings'],
    'guardduty': ['GetInvitationsCount'],
    'iam': ['GetAccountPasswordPolicy', 'GetAccountSummary', 'GetUser', 'GetAccountAuthorizationDetails'],
    'inspector': ['DescribeCrossAccountAccessRole'],
    'iot': [
        'DescribeAccountAuditConfiguration',
        'DescribeEndpoint',
        'DescribeEventConfigurations',
        'GetIndexingConfiguration',
        'GetRegistrationCode',
        'GetV2LoggingOptions',
        'ListV2LoggingLevels',
    ],
    'iotevents': ['DescribeLoggingOptions'],
    'iotthingsgraph': ['DescribeNamespace', 'GetNamespaceDeletionStatus'],
    'kinesis': ['DescribeLimits'],
    'lambda': ['GetAccountSettings'],
    'neptune': ['DescribeEvents'],
    'opsworks': ['DescribeMyUserProfile', 'DescribeUserProfiles', 'DescribeOperatingSystems'],
    'opsworkscm': ['DescribeAccountAttributes'],
    'pinpoint-email': ['GetAccount', 'GetDeliverabilityDashboardOptions'],
    'redshift': ['DescribeStorage', 'DescribeAccountAttributes'],
    'rds': [
        'DescribeAccountAttributes', 'DescribeDBEngineVersions', 'DescribeReservedDBInstancesOfferings',
        'DescribeEvents'
    ],
    'resourcegroupstaggingapi': ['GetResources', 'GetTagKeys', 'DescribeReportCreation', 'GetComplianceSummary'],
    'route53': ['GetTrafficPolicyInstanceCount', 'GetHostedZoneCount', 'GetHealthCheckCount', 'GetGeoLocation'],
    'route53domains': ['ListOperations'],
    'sagemaker': ['ListTrainingJobs'],
    'securityhub': ['GetInvitationsCount'],
    'servicediscovery': ['ListOperations'],
    'ses': ['GetSendQuota', 'GetAccountSendingEnabled'],
    'shield': ['GetSubscriptionState'],
    'sms': ['GetServers'],
    'snowball': ['GetSnowballUsage'],
    'sns': ['GetSMSAttributes', 'ListPhoneNumbersOptedOut'],
    'ssm': ['GetDefaultPatchBaseline'],
    'sts': ['GetSessionToken', 'GetCallerIdentity'],
    'waf': ['GetChangeToken'],
    'waf-regional': ['GetChangeToken'],
    'xray': ['GetEncryptionConfig'],
    'workspaces': ['DescribeAccount', 'DescribeAccountModifications'],
}

PARAMETERS_REQUIRED = {
    'appstream': ['DescribeUserStackAssociations'],
    'batch': ['ListJobs'],
    'cloudformation': ['GetTemplateSummary', 'DescribeStackResources', 'DescribeStackEvents', 'GetTemplate'],
    'cloudhsm': ['DescribeHsm', 'DescribeLunaClient'],
    'cloudtrail': ['GetEventSelectors'],
    'codecommit': ['GetBranch'],
    'codedeploy': ['GetDeploymentTarget', 'ListDeploymentTargets'],
    'cognito-idp': ['GetUser'],
    'directconnect': ['DescribeDirectConnectGatewayAssociations', 'DescribeDirectConnectGatewayAttachments'],
    'ec2': ['DescribeSpotDatafeedSubscription', 'DescribeLaunchTemplateVersions'],
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
    'globalaccelerator': ['DescribeAcceleratorAttributes'],
    'glue': ['GetDataflowGraph', 'GetResourcePolicy'],
    'health': [
        'DescribeEventTypes', 'DescribeEntityAggregates', 'DescribeEvents', 'DescribeEventsForOrganization',
        'DescribeHealthServiceStatusForOrganization'
    ],
    'iot': ['GetLoggingOptions', 'GetEffectivePolicies', 'ListAuditFindings'],
    'kinesis': ['DescribeStreamConsumer', 'ListShards'],
    'kinesisvideo': ['DescribeStream', 'ListTagsForStream'],
    'kinesis-video-archived-media': ['GetHLSStreamingSessionURL'],
    'mediastore': ['DescribeContainer'],
    'opsworks': [
        'DescribeAgentVersions', 'DescribeApps', 'DescribeCommands', 'DescribeDeployments', 'DescribeEcsClusters',
        'DescribeElasticIps', 'DescribeElasticLoadBalancers', 'DescribeInstances', 'DescribeLayers',
        'DescribePermissions', 'DescribeRaidArrays', 'DescribeVolumes'
    ],
    'pricing': ['GetProducts'],
    'redshift': ['DescribeTableRestoreStatus', 'DescribeClusterSecurityGroups'],
    'route53domains': ['GetContactReachabilityStatus'],
    'secretsmanager': ['GetRandomPassword'],
    'shield': ['DescribeSubscription', 'DescribeProtection'],
    'sms': ['GetApp', 'GetAppLaunchConfiguration', 'GetAppReplicationConfiguration'],
    'ssm': ['DescribeAssociation', 'DescribeMaintenanceWindowSchedule', 'ListComplianceItems'],
    # TODO: waf ListLoggingConfigurations may just require fixing
    'waf': ['ListActivatedRulesInRuleGroup', 'ListLoggingConfigurations'],
    'waf-regional': ['ListActivatedRulesInRuleGroup'],
    'workdocs': ['DescribeActivities', 'GetResources'],
    # TODO: worklink ListFleets might just require fixing
    'worklink': ['ListFleets'],
    'xray': ['GetGroup'],
}


def get_services():
    """Return a list of all service names where listable resources can be present"""
    return [service for service in boto3.Session().get_available_services() if service not in SERVICE_BLACKLIST]


def get_verbs(service):
    """Return a list of "Verbs" given a boto3 service client. A "Verb" in this context is
    the first CamelCased word in an API call"""
    client = get_client(service)
    return set(re.sub('([A-Z])', '_\\1', x).split('_')[1] for x in client.meta.method_to_api_mapping.values())


def get_listing_operations(service, region=None, selected_operations=()):
    """Return a list of API calls which (probably) list resources created by the user
    in the given service (in contrast to AWS-managed or default resources)"""
    client = get_client(service, region)
    operations = []
    for operation in client.meta.service_model.operation_names:
        if not any(operation.startswith(prefix) for prefix in VERBS_LISTINGS):
            continue
        op_model = client.meta.service_model.operation_model(operation)
        required_members = op_model.input_shape.required_members if op_model.input_shape else []
        required_members = [m for m in required_members if m != 'MaxResults']
        if required_members:
            continue
        if operation in PARAMETERS_REQUIRED.get(service, []):
            continue
        if operation in AWS_RESOURCE_QUERIES.get(service, []):
            continue
        if operation in NOT_RESOURCE_DESCRIPTIONS.get(service, []):
            continue
        if operation in DEPRECATED_OR_DISALLOWED.get(service, []):
            continue
        if selected_operations and operation not in selected_operations:
            continue
        operations.append(operation)
    return operations


def recreate_caches(update_packaged_values):
    get_endpoint_hosts.recalculate()
    get_service_regions.recalculate()

    if update_packaged_values:
        print('Updating packaged values at:')

        endpoint_hosts_packaged_json = resource_filename(__package__, 'endpoint_hosts.json')
        print(' *', endpoint_hosts_packaged_json)
        dump(get_endpoint_hosts(), open(endpoint_hosts_packaged_json, 'w'))

        service_regions_packaged_json = resource_filename(__package__, 'service_regions.json')
        print(' *', service_regions_packaged_json)
        dump(get_service_regions(), open(service_regions_packaged_json, 'w'))


def packaged_endpoint_hosts():
    return load(resource_stream(__package__, 'endpoint_hosts.json'))


@cache('endpoint_hosts', vary={'boto3_version': boto3.__version__}, cheap_default_func=packaged_endpoint_hosts)
def get_endpoint_hosts():
    print('Extracting endpoint list from boto3 version {} ...'.format(boto3.__version__))

    EC2_REGIONS = set(boto3.Session().get_available_regions('ec2'))
    S3_REGIONS = set(boto3.Session().get_available_regions('s3'))
    ALL_REGIONS = sorted(EC2_REGIONS | S3_REGIONS)
    ALL_SERVICES = get_services()

    result = {}
    for service in ALL_SERVICES:
        print('  ...looking for {} in all regions...'.format(service))
        result[service] = {}
        for region in ALL_REGIONS:
            result[service][region] = boto3.Session(region_name=region).client(service).meta.endpoint_url

    print('...done.')
    return result


def get_endpoint_ip(service_region_host):
    (service, region), host = service_region_host
    try:
        result = gethostbyname(host.split('/')[2])
        return (service, region, result)
    except Exception:
        return (service, region, None)


def get_service_region_ip_in_dns():
    service_region_host = {}
    for service, region_host in get_endpoint_hosts().items():
        for region, host in region_host.items():
            service_region_host[(service, region)] = host
    print('Resolving endpoint IPs to find active endpoints...')
    result = ThreadPool(128).map(get_endpoint_ip, service_region_host.items())
    print('...done')
    return result


def packaged_service_regions():
    return load(resource_stream(__package__, 'service_regions.json'))


@cache('service_regions', vary={'boto3_version': boto3.__version__}, cheap_default_func=packaged_service_regions)
def get_service_regions():
    service_regions = {}
    for service, region, ip in get_service_region_ip_in_dns():
        service_regions.setdefault(service, set())
        if ip is not None:
            service_regions[service].add(region)
    return {service: list(regions) for service, regions in service_regions.items()}


def get_regions_for_service(requested_service, requested_regions=()):
    """Given a service name, return a list of region names where this service can have resources,
    restricted by a possible set of regions."""
    if requested_service in ('iam', 'cloudfront', 's3', 'route53'):
        return [None]
    regions = set(get_service_regions().get(requested_service, []))
    return list(regions) if not requested_regions else list(sorted(set(regions) & set(requested_regions)))


def introspect_regions_for_service():
    """Introspect and compare guessed and boto3-defined regions"""
    print('Comparing service/region pairs reported by boto3 and found via DNS queries')
    print('=' * 100)
    guessed_regions = get_service_regions()
    m = defaultdict(set)
    for service, guessed in sorted(guessed_regions.items()):
        reported = boto3.Session().get_available_regions(service)
        if set(reported) == set(guessed):
            print(service, 'guessed.')
        if set(guessed) - set(reported):
            print(service, 'more than reported:', set(guessed) - set(reported))
        if set(reported) - set(guessed):
            print(service, 'less than reported:', set(reported) - set(guessed))
        m[frozenset(map(str, guessed))].add(service)

    print()
    print('Listing service/region pairs by sets of supported regions')
    print('=' * 100)
    for regions, services in sorted(m.items()):
        print('-' * 80)
        print('in the', len(regions), 'regions', ', '.join(sorted(regions)))
        print('...there are these', len(services), 'services:')
        for service in sorted(services):
            print(' -', service)
