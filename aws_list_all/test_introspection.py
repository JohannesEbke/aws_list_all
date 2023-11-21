from .introspection import (
    get_endpoint_hosts, get_listing_operations, get_regions_for_service, get_service_regions, get_services,
    introspect_regions_for_service
)


def test_get_services():
    services = get_services()
    assert len(services) > 160
    assert 'ec2' in services
    assert 'route53' in services


def test_get_endpoint_hosts():
    services = get_services()
    endpoint_hosts = get_endpoint_hosts()
    assert set(services) - set(endpoint_hosts) == set()
    services_with_no_endpoint = [service for service in services if len(endpoint_hosts[service]) == 0]
    # Services with no endpoint means they should probably go to the SERVICE_IGNORE_LIST
    assert not services_with_no_endpoint


def test_get_service_regions():
    services = get_services()
    regions = get_service_regions()
    assert set(services) - set(regions) == set()
    services_with_no_region = {service for service in services if len(regions[service]) == 0}
    expected_no_region = {'route53-recovery-cluster', 'mobile'}
    # Services with no region that have no listings means they should probably go to the SERVICE_IGNORE_LIST
    assert services_with_no_region == expected_no_region


def test_get_regions_for_service():
    requested_regions = ('us-east-2', 'eu-west-1', 'nonexistent')
    assert set(get_regions_for_service('ec2', requested_regions=requested_regions)) == set(('us-east-2', 'eu-west-1'))


def test_introspect_regions_for_service():
    introspect_regions_for_service()


def test_get_listing_operations():
    expected_no_listings = {
        'account',
        'amplifyuibuilder',
        'appconfigdata',
        'application-autoscaling',
        'bedrock-runtime',
        'braket',  # TODO: Failure of heuristic, see issue #38
        'budgets',
        'chime-sdk-meetings',
        'chime-sdk-messaging',
        'cloudtrail-data',
        'connect-contact-lens',
        'connectparticipant',
        'controltower',
        'ebs',
        'ec2-instance-connect',
        'forecastquery',
        'glacier',
        'health',
        'honeycode',
        'identitystore',
        'iot-jobs-data',
        'iotevents-data',
        'kinesis-video-signaling',
        'kinesis-video-webrtc-storage',
        'lex-runtime',
        'lexv2-runtime',
        'managedblockchain-query',
        'marketplace-catalog',
        'marketplace-entitlement',
        'marketplacecommerceanalytics',
        'mediaconvert',
        'meteringmarketplace',
        'payment-cryptography-data',
        'personalize-events',
        'personalize-runtime',
        'pi',
        'pinpoint-sms-voice',
        'pricing',
        'qldb-session',
        'quicksight',
        'rbin',
        'rds-data',
        'resourcegroupstaggingapi',
        'sagemaker-a2i-runtime',
        'sagemaker-edge',
        'sagemaker-featurestore-runtime',
        'sagemaker-metrics',
        'sagemaker-runtime',
        'sso',
        'sso-oidc',
        'sts',
        'swf',
        'wafv2',
        'workdocs',
        'workmailmessageflow',
    }

    services_with_no_listings = set()
    for service in get_services():
        print('Testing', service)
        if len(get_listing_operations(service, region='us-east-1')) == 0:
            services_with_no_listings.add(service)

    assert expected_no_listings - services_with_no_listings == set(), (
        'Extra services gained listings, please check if they are valid '
        'using "aws-list-all introspect list-operations --service X"'
    )
    assert services_with_no_listings - expected_no_listings == set(), 'Some services have no listings, please check!'
