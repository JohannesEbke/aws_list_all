from __future__ import print_function

import re
import importlib_resources
from collections import defaultdict
from json import load, dump
from multiprocessing.pool import ThreadPool
from socket import gethostbyname, gaierror

import boto3

from app_json_file_cache import AppCache

from .client import get_client

cache = AppCache('aws_list_all')

VERBS_LISTINGS = ['Describe', 'Get', 'List']

SERVICE_IGNORE_LIST = [
    'alexaforbusiness',  # TODO: Mostly organization-specific calls and would need to be queried differently
    'apigatewaymanagementapi',  # This API allows management of deployed APIs, and requires an endpoint per API.
    'backupstorage',  # This seems to be an API centerered around Jobs, no listings possible
    'cloudsearchdomain',  # Domain-specific endpoint required
    'iotthingsgraph',  # Discontinued
    'kinesis-video-archived-media',  # API operating on stream-specific endpoints
    'kinesis-video-media',  # API operating on stream-specific endpoints
    'macie',  # This service has been deprecated and turned off
    'managedblockchain',  # TODO: Unclear, does not have a region
    'mediastore-data',  # Mediastore Container-specific endpoint required
    'neptunedata',  # Data access API
    's3control',  # TODO: Account-ID specific endpoint required
    'worklink',  # Seems to have no API?
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

# This lists API calls that do return a list of resource-like objects which cannot be influenced by the user
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
    'codestar-notifications': ['ListEventTypes'],
    'devicefarm': ['ListDevices', 'ListOfferings', 'ListOfferingTransactions'],
    'directconnect': ['DescribeLocations'],
    'dynamodb': ['DescribeEndpoints'],
    'dms': ['DescribeEndpointTypes', 'DescribeOrderableReplicationInstances', 'DescribeEventCategories'],
    'docdb': ['DescribeCertificates', 'DescribeDBEngineVersions', 'DescribeEventCategories'],
    'ec2': [
        'DescribeAggregateIdFormat',
        'DescribeCapacityProviders',
        'DescribeAvailabilityZones',
        'DescribeHostReservationOfferings',
        'DescribeIdFormat',
        'DescribeInstanceTypeOfferings',
        'DescribeInstanceTypes',
        'DescribeManagedPrefixLists',
        'DescribePrefixLists',
        'DescribeRegions',
        'DescribeReservedInstancesOfferings',
        'DescribeSpotPriceHistory',
        'DescribeVpcClassicLinkDnsSupport',
        'DescribeVpcEndpointServices',
        'GetVpnConnectionDeviceTypes',
    ],
    'eks': ['DescribeAddonVersions'],
    'elasticache': ['DescribeCacheParameterGroups', 'DescribeCacheEngineVersions', 'DescribeServiceUpdates'],
    'elasticbeanstalk': [
        'ListAvailableSolutionStacks',
        'ListPlatformBranches',
        'PlatformSummaryList',
    ],
    'elastictranscoder': ['ListPresets'],
    'elb': ['DescribeLoadBalancerPolicyTypes', 'DescribeLoadBalancerPolicies'],
    'elbv2': ['DescribeSSLPolicies'],
    'es': ['DescribeReservedElasticsearchInstanceOfferings', 'GetCompatibleElasticsearchVersions'],
    'fis': ['ListActions'],
    'groundstation': ['ListGroundStations'],
    'inspector': ['ListRulesPackages'],
    'kafka': ['GetCompatibleKafkaVersions', 'ListKafkaVersions'],
    'lex-models': ['GetBuiltinIntents', 'GetBuiltinSlotTypes'],
    'lightsail': [
        'GetBlueprints', 'GetBundles', 'GetDistributionBundles', 'GetRegions', 'GetRelationalDatabaseBlueprints',
        'GetRelationalDatabaseBundles'
    ],
    'mediaconvert': ['DescribeEndpoints'],
    'medialive': ['ListOfferings'],
    'mobile': ['ListBundles'],
    'mq': ['DescribeBrokerInstanceOptions', 'DescribeBrokerEngineTypes'],
    'neptune': ['DescribeDBEngineVersions', 'DescribeEventCategories'],
    'opensearch': ['DescribeReservedInstanceOfferings'],
    'outposts': ['ListCatalogItems'],
    'personalize': ['ListRecipes'],
    'pricing': ['DescribeServices'],
    'polly': ['DescribeVoices'],
    'ram': ['ListPermissions', 'ListResourceTypes'],  # TODO: ListPermissions may possibly also return user-created ones
    'rds': ['DescribeDBEngineVersions', 'DescribeSourceRegions', 'DescribeCertificates', 'DescribeEventCategories'],
    'redshift': [
        'DescribeClusterVersions',
        'DescribeReservedNodeOfferings',
        'DescribeOrderableClusterOptions',
        'DescribeEventCategories',
        'DescribeClusterTracks',
    ],
    'resiliencehub': ['ListSuggestedResiliencyPolicies'],
    'resource-explorer-2': ['ListSupportedResourceTypes'],
    'route53': ['GetCheckerIpRanges', 'ListGeoLocations'],
    'route53domains': ['ListPrices'],
    'savingsplans': ['DescribeSavingsPlansOfferingRates', 'DescribeSavingsPlansOfferings'],
    'securityhub': ['DescribeStandards', 'DescribeProducts', 'GetEnabledStandards', 'ListEnabledProductsForImport'],
    'service-quotas': ['ListServices'],
    'signer': ['ListSigningPlatforms'],
    'ssm': ['DescribeAvailablePatches', 'GetInventorySchema'],
    'synthetics': ['DescribeRuntimeVersions'],
    'timestream-query': ['DescribeEndpoints'],
    'timestream-write': ['DescribeEndpoints'],
    'transfer': ['ListSecurityPolicies'],
    'translate': ['ListLanguages'],
    'xray': ['GetSamplingRules'],
}

# This lists API calls that do not return resources or resource-like objects.
#
# It has become a bit mixed up with the AWS_RESOURCE_QUERIES list, yet the idea here is that these calls may
# still be used later for change tracking, e.g. tracking account limits over time with DescribeAccountLimits.
NOT_RESOURCE_DESCRIPTIONS = {
    'apigateway': ['GetAccount'],
    'account': ['GetContactInformation', 'ListRegions'],
    'acm': ['GetAccountConfiguration'],
    'auditmanager': ['GetAccountStatus'],
    'autoscaling': ['DescribeAccountLimits'],
    'alexaforbusiness': ['GetInvitationConfiguration'],
    'appflow': ['DescribeConnectors', 'ListConnectorEntities', 'ListConnectors'],
    'athena': ['ListQueryExecutions'],
    'backup': ['DescribeGlobalSettings', 'DescribeRegionSettings'],
    'chime': ['GetGlobalSettings', 'GetMessagingSessionEndpoint'],
    'chime-sdk-messaging': ['GetMessagingSessionEndpoint'],
    'cloudformation': ['DescribeAccountLimits'],
    'cloudwatch': ['DescribeAlarmHistory'],
    'codebuild': ['ListBuilds'],
    'config': [
        'GetComplianceSummaryByResourceType', 'GetComplianceSummaryByConfigRule', 'DescribeComplianceByConfigRule',
        'DescribeComplianceByResource', 'DescribeConfigRuleEvaluationStatus', 'GetDiscoveredResourceCounts'
    ],
    'compute-optimizer': ['GetEnrollmentStatus'],
    'dax': ['DescribeDefaultParameters', 'DescribeParameterGroups'],
    'devicefarm': ['GetAccountSettings', 'GetOfferingStatus'],
    'devops-guru': [
        'DescribeOrganizationHealth',
        'DescribeAccountHealth',
        'DescribeServiceIntegration',
        'GetCostEstimation',
    ],
    'directconnect': ['DescribeCustomerMetadata'],
    'discovery': ['GetDiscoverySummary'],
    'dms': ['DescribeAccountAttributes', 'DescribeApplicableIndividualAssessments', 'DescribeEventCategories'],
    'docdb': ['DescribeEvents'],
    'ds': ['GetDirectoryLimits'],
    'dynamodb': ['DescribeLimits'],
    'ec2': [
        'DescribeAccountAttributes',
        'DescribeDhcpOptions',
        'DescribeInstanceEventNotificationAttributes',
        'DescribePrincipalIdFormat',
        'DescribeVpcClassicLink',
        'DescribeVpcClassicLinkDnsSupport',
        'GetAwsNetworkPerformanceData',
        'GetEbsDefaultKmsKeyId',
        'GetEbsEncryptionByDefault',
        'GetImageBlockPublicAccessState',
        'GetSerialConsoleAccessStatus',
        'GetSnapshotBlockPublicAccessState',
        'InstanceTagAttribute',
    ],
    'ecr': ['GetAuthorizationToken', 'DescribeRegistry', 'GetRegistryPolicy', 'GetRegistryScanningConfiguration'],
    'ecr-public': ['GetAuthorizationToken', 'GetRegistryCatalogData'],
    'ecs': ['DescribeClusters'],  # This gives duplicates from ListClusters, and also includes deleted clusters
    'efs': ['DescribeAccountPreferences', 'DescribeReplicationConfigurations'],
    'elastic-inference': ['DescribeAcceleratorTypes'],
    'elasticache': ['DescribeReservedCacheNodesOfferings'],
    'elasticbeanstalk': ['DescribeAccountAttributes', 'DescribeEvents'],
    'elb': ['DescribeAccountLimits'],
    'elbv2': ['DescribeAccountLimits'],
    'emr': ['DescribeReleaseLabel', 'GetBlockPublicAccessConfiguration'],
    'es': ['ListElasticsearchVersions'],
    'events': ['DescribeEventBus'],
    'fms': ['GetAdminAccount', 'GetNotificationChannel'],
    'frauddetector': ['GetKMSEncryptionKey'],
    'gamelift': ['DescribeEC2InstanceLimits', 'DescribeMatchmakingConfigurations', 'DescribeMatchmakingRuleSets'],
    'glue': ['GetCatalogImportStatus', 'GetDataCatalogEncryptionSettings'],
    'guardduty': ['GetInvitationsCount'],
    'greengrassv2': ['GetServiceRoleForAccount'],
    'health': ['DescribeAffectedEntitiesForOrganization'],
    'healthlake': ['DescribeFHIRDatastore'],
    'iam': ['GetAccountPasswordPolicy', 'GetAccountSummary', 'GetUser', 'GetAccountAuthorizationDetails'],
    'iotdeviceadvisor': ['GetEndpoint'],
    'iotfleetwise': ['GetLoggingOptions', 'GetRegisterAccountStatus'],
    'iotsitewise': [
        'DescribeDefaultEncryptionConfiguration',
        'DescribeLoggingOptions',
        'DescribeStorageConfiguration',
    ],
    'inspector': ['DescribeCrossAccountAccessRole'],
    'inspector2': [
        'DescribeOrganizationConfiguration',
        'GetConfiguration',
        'GetDelegatedAdminAccount',
        'GetFindingsReportStatus',
        'ListCoverageStatistics',
    ],
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
    'iotwireless': ['GetEventConfigurationByResourceTypes', 'GetServiceEndpoint'],
    'iotthingsgraph': ['DescribeNamespace', 'GetNamespaceDeletionStatus'],
    'kinesis': ['DescribeLimits'],
    'lambda': ['GetAccountSettings'],
    'lakeformation': ['GetDataLakeSettings'],
    'macie2': [
        'GetClassificationExportConfiguration',
        'GetInvitationsCount',
        'GetUsageStatistics',
        'GetUsageTotals',
    ],
    'mediaconvert': ['GetPolicy'],
    'migrationhubstrategy': ['GetPortfolioSummary'],
    'neptune': ['DescribeEvents'],
    'networkmanager': ['ListOrganizationServiceAccessStatus'],
    'opsworks': ['DescribeMyUserProfile', 'DescribeUserProfiles', 'DescribeOperatingSystems'],
    'opsworkscm': ['DescribeAccountAttributes'],
    'organizations': ['DescribeOrganization'],
    'pinpoint-email': ['GetAccount', 'GetDeliverabilityDashboardOptions'],
    'proton': ['GetAccountSettings'],
    'redshift': ['DescribeStorage', 'DescribeAccountAttributes'],
    'rds': [
        'DescribeAccountAttributes', 'DescribeDBEngineVersions', 'DescribeReservedDBInstancesOfferings',
        'DescribeEvents'
    ],
    'resourcegroupstaggingapi': ['GetResources', 'GetTagKeys', 'DescribeReportCreation', 'GetComplianceSummary'],
    'route53': ['GetTrafficPolicyInstanceCount', 'GetHostedZoneCount', 'GetHealthCheckCount', 'GetGeoLocation'],
    'route53domains': ['ListOperations'],
    'route53resolver': ['ListResolverQueryLogConfigAssociations', 'ListResolverQueryLogConfigs'],
    'sagemaker': ['ListTrainingJobs', 'GetSagemakerServicecatalogPortfolioStatus'],
    'securityhub': ['GetInvitationsCount', 'DescribeHub', 'DescribeOrganizationConfiguration'],
    'servicediscovery': ['ListOperations'],
    'ses': ['GetSendQuota', 'GetAccountSendingEnabled'],
    'sesv2': ['GetAccount', 'GetDeliverabilityDashboardOptions'],
    'shield': ['GetSubscriptionState', 'DescribeAttackStatistics'],
    'sms': ['GetServers'],
    'snowball': ['GetSnowballUsage'],
    'sns': ['GetSMSAttributes', 'ListPhoneNumbersOptedOut', 'GetSMSSandboxAccountStatus'],
    'ssm': ['GetDefaultPatchBaseline'],
    'sts': ['GetSessionToken', 'GetCallerIdentity'],
    'waf': ['GetChangeToken'],
    'waf-regional': ['GetChangeToken'],
    'xray': ['GetEncryptionConfig'],
    'workspaces': ['DescribeAccount', 'DescribeAccountModifications'],
}

# TODO wafv2 ListWebAcls needs a scope parameter - this may not be caught here!

PARAMETERS_REQUIRED = {
    'appstream': ['DescribeUserStackAssociations', 'DescribeApplicationFleetAssociations'],
    'application-insights': ['ListConfigurationHistory'],
    'batch': ['ListJobs'],
    'chime': ['ListChannelMembershipsForAppInstanceUser', 'ListChannelsModeratedByAppInstanceUser'],
    'cloudformation': [
        'DescribeStackEvents', 'DescribeStackResources', 'DescribeType', 'GetTemplate', 'GetTemplateSummary',
        'ListTypeVersions'
    ],
    'cloudfront': [
        'GetRealtimeLogConfig',
        'ListDistributionsByRealtimeLogConfig',
    ],
    'cloudhsm': ['DescribeHsm', 'DescribeLunaClient'],
    'cloudtrail': ['GetEventSelectors'],
    'codebuild': ['ListBuildBatchesForProject'],
    'codecommit': ['GetBranch'],
    'codedeploy': ['GetDeploymentTarget', 'ListDeploymentTargets'],
    'cognito-idp': ['GetUser'],
    'devops-guru': ['DescribeFeedback'],
    'directconnect': ['DescribeDirectConnectGatewayAssociations', 'DescribeDirectConnectGatewayAttachments'],
    'dms': ['ListTagsForResource'],
    'ec2': [
        'DescribeLaunchTemplateVersions',
        # This works without parameters, returns default sec group rules
        'DescribeSecurityGroupRules',
        'DescribeSpotDatafeedSubscription',
        'GetAssociatedEnclaveCertificateIamRoles',
        'GetTransitGatewayMulticastDomainAssociations',
    ],
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
    'glue': ['GetDataflowGraph', 'GetResourcePolicy', 'GetSchemaVersion'],
    'health': [
        'DescribeEventTypes', 'DescribeEntityAggregates', 'DescribeEvents', 'DescribeEventsForOrganization',
        'DescribeHealthServiceStatusForOrganization'
    ],
    'iot': ['GetLoggingOptions', 'GetEffectivePolicies', 'ListAuditFindings', 'ListDetectMitigationActionsExecutions'],
    'iotsitewise': [
        'DescribeTimeSeries',
        'GetAssetPropertyValue',
        'GetAssetPropertyValueHistory',
        'ListAccessPolicies',
        'ListAssets',
    ],
    'kinesis': ['DescribeStreamConsumer', 'ListShards'],
    'kinesisvideo': [
        'DescribeImageGenerationConfiguration',
        'DescribeNotificationConfiguration',
        'DescribeSignalingChannel',
        'DescribeStream',
        'ListTagsForStream',
    ],
    'kinesis-video-archived-media': ['GetHLSStreamingSessionURL'],
    'lightsail': ['GetDistributionLatestCacheReset'],
    'lookoutmetrics': ['GetSampleData'],
    'mediastore': ['DescribeContainer'],
    'network-firewall': [
        'DescribeFirewall',
        'DescribeFirewallPolicy',
        'DescribeLoggingConfiguration',
        'DescribeRuleGroup',
        'DescribeRuleGroupMetadata',
    ],
    'opsworks': [
        'DescribeAgentVersions', 'DescribeApps', 'DescribeCommands', 'DescribeDeployments', 'DescribeEcsClusters',
        'DescribeElasticIps', 'DescribeElasticLoadBalancers', 'DescribeInstances', 'DescribeLayers',
        'DescribePermissions', 'DescribeRaidArrays', 'DescribeVolumes'
    ],
    'personalize-runtime': ['GetRecommendations'],
    'pricing': ['GetProducts'],
    'redshift': ['DescribeTableRestoreStatus', 'DescribeClusterSecurityGroups', 'DescribeReservedNodeExchangeStatus'],
    'redshift-serverless': ['GetSnapshot'],
    'resource-groups': ['GetGroup', 'GetGroupConfiguration', 'GetGroupQuery', 'ListGroupResources'],
    'robomaker': ['GetWorldTemplateBody'],
    'route53domains': ['GetContactReachabilityStatus'],
    'schemas': ['GetResourcePolicy'],
    'sagemaker': ['ListAssociations', 'ListPipelineExecutionSteps'],
    'secretsmanager': ['GetRandomPassword'],
    'servicecatalog': [
        'DescribeProduct',
        'DescribeProductAsAdmin',
        'DescribeProvisionedProduct',
        'DescribeProvisioningArtifact',
        'DescribeProvisioningParameters',
        'GetProvisionedProductOutputs',
    ],
    'shield': ['DescribeSubscription', 'DescribeProtection'],
    'sms': ['GetApp', 'GetAppLaunchConfiguration', 'GetAppReplicationConfiguration'],
    'ssm': [
        'DescribeAssociation',
        'DescribeMaintenanceWindowSchedule',
        'ListComplianceItems',
        'ListOpsItemRelatedItems',
    ],
    # TODO: waf ListLoggingConfigurations may just require fixing
    'waf': ['ListActivatedRulesInRuleGroup', 'ListLoggingConfigurations'],
    'wafv2': ['GetRuleGroup'],
    'waf-regional': ['ListActivatedRulesInRuleGroup'],
    'workdocs': ['DescribeActivities', 'GetResources'],
    # TODO: worklink ListFleets might just require fixing
    'worklink': ['ListFleets'],
    'xray': ['GetGroup'],
}


def get_services():
    """Return a list of all service names where listable resources can be present"""
    return [
        service for service in sorted(boto3.Session().get_available_services()) if service not in SERVICE_IGNORE_LIST
    ]


def get_verbs(service):
    """Return a list of "Verbs" given a boto3 service client. A "Verb" in this context is
    the first CamelCased word in an API call"""
    client = get_client(service)
    return set(re.sub('([A-Z])', '_\\1', x).split('_')[1] for x in client.meta.method_to_api_mapping.values())


def get_listing_operations(service, region=None, selected_operations=(), profile=None):
    """Return a list of API calls which (probably) list resources created by the user
    in the given service (in contrast to AWS-managed or default resources)"""
    client = get_client(service, region, profile)
    operations = []
    for operation in sorted(client.meta.service_model.operation_names):
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

        ref_endpoint_hosts = importlib_resources.files(__package__) / 'endpoint_hosts.json'
        with importlib_resources.as_file(ref_endpoint_hosts) as endpoint_hosts_packaged_json:
            print(' *', endpoint_hosts_packaged_json)
            dump(get_endpoint_hosts(), open(endpoint_hosts_packaged_json, 'w'), sort_keys=True, indent=4)

        ref_service_regions = importlib_resources.files(__package__) / 'service_regions.json'
        with importlib_resources.as_file(ref_service_regions) as service_regions_packaged_json:
            print(' *', service_regions_packaged_json)
            dump(get_service_regions(), open(service_regions_packaged_json, 'w'), sort_keys=True, indent=4)


def packaged_endpoint_hosts():
    ref_endpoint_hosts = importlib_resources.files(__package__) / 'endpoint_hosts.json'
    with ref_endpoint_hosts.open('rb') as endpoint_hosts_packaged_json:
        return load(endpoint_hosts_packaged_json)


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
            meta = get_client(service, region=region).meta
            # In some services, different operations must access different host prefixes ("api.", "env.").
            # This means that the endpoint_url itself may not point to any host, defeating our heuristic.
            # Therefore, we only pick the base URL if at least one operation accesses it, otherwise we pick the
            # alphabetically first host prefix.
            endpoint_prefixes = set(
                meta.service_model.operation_model(op_name).endpoint.get('hostPrefix')
                for op_name in meta.service_model.operation_names
                if meta.service_model.operation_model(op_name).endpoint
            )
            if None in endpoint_prefixes or not endpoint_prefixes:
                result[service][region] = [meta.endpoint_url]
            else:
                assert meta.endpoint_url.startswith("https://"), meta.endpoint_url
                result[service][region] = []
                prefixes = sorted(endpoint_prefixes)
                if any(pf.endswith(".") for pf in prefixes):
                    result[service][region] = [meta.endpoint_url]
                for prefix in prefixes:
                    result[service][region].append("https://" + prefix + meta.endpoint_url[len("https://"):])
    print('...done.')
    return result


def get_endpoint_ip(service_region_hosts):
    (service, region), hosts = service_region_hosts
    result = None
    for host in hosts:
        try:
            result = gethostbyname(host.split('/')[2])
        except gaierror as ex:
            if ex.errno != -5:  # -5 is "No address associated with hostname"
                raise
        if result:
            break
    return (service, region, result)


def get_service_region_ip_in_dns():
    service_region_hosts = {}
    for service, region_hosts in get_endpoint_hosts().items():
        for region, hosts in region_hosts.items():
            service_region_hosts[(service, region)] = hosts
    print('Resolving endpoint IPs to find active endpoints...')
    result = ThreadPool(128).map(get_endpoint_ip, service_region_hosts.items())
    print('...done')
    return result


def packaged_service_regions():
    ref_service_regions = importlib_resources.files(__package__) / 'service_regions.json'
    with ref_service_regions.open('rb') as service_regions_packaged_json:
        return load(service_regions_packaged_json)


@cache('service_regions', vary={'boto3_version': boto3.__version__}, cheap_default_func=packaged_service_regions)
def get_service_regions():
    service_regions = {}
    for service, region, ip in get_service_region_ip_in_dns():
        service_regions.setdefault(service, set())
        if ip is not None:
            service_regions[service].add(region)
    return {service: sorted(list(regions)) for service, regions in service_regions.items()}


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
