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
    # Services with no endpoint means they should probably go to the SERVICE_BLACKLIST
    assert not services_with_no_endpoint


def test_get_service_regions():
    services = get_services()
    regions = get_service_regions()
    assert set(services) - set(regions) == set()
    services_with_no_region = [service for service in services if len(regions[service]) == 0]
    # Services with no region means they should probably go to the SERVICE_BLACKLIST
    assert not services_with_no_region


def test_get_regions_for_service():
    requested_regions = ('us-east-2', 'eu-west-1', 'nonexistent')
    assert set(get_regions_for_service('ec2', requested_regions=requested_regions)) == set(('us-east-2', 'eu-west-1'))


def test_introspect_regions_for_service():
    introspect_regions_for_service()


def test_get_listing_operations():
    expected_no_listings = {
        'application-autoscaling',
        'budgets',
        'braket',  # TODO: Failure of heuristic, see issue #38
        'connect',
        'connectparticipant',
        'ebs',
        'ec2-instance-connect',
        'forecastquery',
        'glacier',
        'health',
        'honeycode',
        'identitystore',
        'iot-data',
        'iot-jobs-data',
        'iotevents-data',
        'iotthingsgraph',
        'kinesis-video-signaling',
        'lex-runtime',
        'marketplace-catalog',
        'marketplace-entitlement',
        'marketplacecommerceanalytics',
        'mediaconvert',
        'meteringmarketplace',
        'personalize-events',
        'personalize-runtime',
        'pi',
        'pinpoint-sms-voice',
        'pricing',
        'qldb-session',
        'quicksight',
        'rds-data',
        'resourcegroupstaggingapi',
        'sagemaker-runtime',
        'sagemaker-a2i-runtime',
        'sso',
        'sso-oidc',
        'sts',
        'swf',
        'textract',
        'workdocs',
        'worklink',
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
