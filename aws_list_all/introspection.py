import re

import boto3

from .client import get_client

VERBS_LISTINGS = ['Describe', 'Get', 'List']

SERVICE_BLACKLIST = [
    'cur',  # costs and usage reports
    'discovery',  # requires manual whitelisting
    'support',  # support has no payable resources
]

DEPRECATED_OR_DISALLOWED = {
    # service need opt-in
    'alexaforbusiness': [
        'GetDevice',
        'GetProfile',
        'GetRoom',
        'GetSkillGroup',
        'ListSkills',
    ],
    # service need opt-in
    'cloudhsm': [
        'ListHapgs',
        'ListHsms',
        'ListLunaClients',
    ],
    'directconnect': ['DescribeInterconnects'],  # needs opt-in
    'dms': [
        # migration service needs to be created
        'DescribeReplicationTaskAssessmentResults'
    ],
    'ec2': ['DescribeScheduledInstances', 'DescribeReservedInstancesListings'],  # needs opt-in
    'emr': ['DescribeJobFlows'],  # deprecated
    'greengrass': ['GetServiceRoleForAccount'],  # Role needs to be created
    'iam': ['GetCredentialReport'],  # credential report needs to be created
    'iot': ['DescribeDefaultAuthorizer'],  # authorizer needs to be created
    'mediaconvert': ['ListJobTemplates', 'ListJobs', 'ListPresets',
                     'ListQueues'],  # service needs customer-specific endpoint
    'mturk': [
        'GetAccountBalance', 'ListBonusPayments', 'ListHITs', 'ListQualificationRequests', 'ListReviewableHITs',
        'ListWorkerBlocks'
    ],  # service needs opt-in
    'servicecatalog': ['ListTagOptions'],  # requires a Tag Option Migration
    'workdocs': ['DescribeUsers'],  # need to be AWS-root
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
        'DescribeVpcClassicLinkDnsSupport', 'DescribeAggregateIdFormat'
    ],
    'elasticache': ['DescribeCacheParameterGroups', 'DescribeCacheEngineVersions'],
    'elasticbeanstalk': ['ListAvailableSolutionStacks', 'PlatformSummaryList'],
    'elastictranscoder': ['ListPresets'],
    'elb': ['DescribeLoadBalancerPolicyTypes', 'DescribeLoadBalancerPolicies'],
    'elbv2': ['DescribeSSLPolicies'],
    'inspector': ['ListRulesPackages'],
    'lex-models': ['GetBuiltinIntents', 'GetBuiltinSlotTypes'],
    'lightsail': ['GetBlueprints', 'GetBundles', 'GetRegions'],
    'mediaconvert': ['DescribeEndpoints'],
    'pricing': ['DescribeServices'],
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
        'DescribeComplianceByResource', 'DescribeConfigRuleEvaluationStatus', 'GetDiscoveredResourceCounts'
    ],
    'dax': ['DescribeDefaultParameters', 'DescribeParameterGroups'],
    'devicefarm': ['GetAccountSettings', 'GetOfferingStatus'],
    'dms': ['DescribeAccountAttributes', 'DescribeEventCategories'],
    'ds': ['GetDirectoryLimits'],
    'dynamodb': ['DescribeLimits'],
    'ec2': [
        'DescribeAccountAttributes', 'DescribeDhcpOptions', 'DescribeVpcClassicLink',
        'DescribeVpcClassicLinkDnsSupport', 'DescribePrincipalIdFormat'
    ],
    'ecr': ['GetAuthorizationToken'],
    'elasticache': ['DescribeReservedCacheNodesOfferings'],
    'elasticbeanstalk': ['DescribeAccountAttributes', 'DescribeEvents'],
    'elb': ['DescribeAccountLimits'],
    'elbv2': ['DescribeAccountLimits'],
    'es': ['ListElasticsearchVersions'],
    'events': ['DescribeEventBus'],
    'gamelift': ['DescribeEC2InstanceLimits', 'DescribeMatchmakingConfigurations', 'DescribeMatchmakingRuleSets'],
    'glue': ['GetCatalogImportStatus'],
    'guardduty': ['GetInvitationsCount'],
    'iam': ['GetAccountPasswordPolicy', 'GetAccountSummary', 'GetUser', 'GetAccountAuthorizationDetails'],
    'inspector': ['DescribeCrossAccountAccessRole'],
    'iot': [
        'GetRegistrationCode', 'DescribeEndpoint', 'DescribeEventConfigurations', 'GetIndexingConfiguration',
        'GetV2LoggingOptions', 'ListV2LoggingLevels'
    ],
    'kinesis': ['DescribeLimits'],
    'lambda': ['GetAccountSettings'],
    'opsworks': ['DescribeMyUserProfile', 'DescribeUserProfiles', 'DescribeOperatingSystems'],
    'opsworkscm': ['DescribeAccountAttributes'],
    'rds': ['DescribeAccountAttributes', 'DescribeDBEngineVersions', 'DescribeReservedDBInstancesOfferings'],
    'resourcegroupstaggingapi': ['GetResources', 'GetTagKeys'],
    'route53': ['GetTrafficPolicyInstanceCount', 'GetHostedZoneCount', 'GetHealthCheckCount', 'GetGeoLocation'],
    'ses': ['GetSendQuota', 'GetAccountSendingEnabled'],
    'shield': ['GetSubscriptionState'],
    'sms': ['GetServers'],
    'snowball': ['GetSnowballUsage'],
    'sns': ['GetSMSAttributes', 'ListPhoneNumbersOptedOut'],
    'ssm': ['GetDefaultPatchBaseline'],
    'sts': ['GetSessionToken', 'GetCallerIdentity'],
    'waf': ['GetChangeToken'],
    'waf-regional': ['GetChangeToken'],
}

PARAMETERS_REQUIRED = {
    'batch': ['ListJobs'],
    'cloudformation': ['GetTemplateSummary', 'DescribeStackResources', 'DescribeStackEvents', 'GetTemplate'],
    'cloudhsm': ['DescribeHsm', 'DescribeLunaClient'],
    'cloudtrail': ['GetEventSelectors'],
    'codecommit': ['GetBranch'],
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
    'glue': ['GetDataflowGraph'],
    'health': ['DescribeEventTypes', 'DescribeEntityAggregates', 'DescribeEvents'],
    'iot': ['GetLoggingOptions', 'GetEffectivePolicies'],
    'kinesis': ['ListShards'],
    'kinesisvideo': ['DescribeStream', 'ListTagsForStream'],
    'opsworks': [
        'DescribeAgentVersions', 'DescribeApps', 'DescribeCommands', 'DescribeDeployments', 'DescribeEcsClusters',
        'DescribeElasticIps', 'DescribeElasticLoadBalancers', 'DescribeInstances', 'DescribeLayers',
        'DescribePermissions', 'DescribeRaidArrays', 'DescribeVolumes'
    ],
    'pricing': ['GetProducts'],
    'redshift': ['DescribeTableRestoreStatus', 'DescribeClusterSecurityGroups'],
    'route53domains': ['GetContactReachabilityStatus'],
    'shield': ['DescribeSubscription', 'ListProtections'],
    'ssm': ['DescribeAssociation', 'ListComplianceItems'],
    'waf-regional': ['ListActivatedRulesInRuleGroup'],
    'workdocs': ['DescribeActivities'],  # need to be root
}


def get_services():
    """Return a list of all service names where listable resources can be present"""
    return [service for service in boto3.Session().get_available_services() if service not in SERVICE_BLACKLIST]


def get_verbs(service):
    """Return a list of "Verbs" given a boto3 service client. A "Verb" in this context is
    the first CamelCased word in an API call"""
    client = get_client(service)
    return set(re.sub("([A-Z])", "_\\1", x).split("_")[1] for x in client.meta.method_to_api_mapping.values())


def get_listing_operations(service, region=None, selected_operations=()):
    """Return a list of API calls which (probably) list resources created by the user
    in the given service (in contrast to AWS-managed or default resources)"""
    client = get_client(service, region)
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
        if selected_operations and operation not in selected_operations:
            continue
        operations.append(operation)
    return operations
