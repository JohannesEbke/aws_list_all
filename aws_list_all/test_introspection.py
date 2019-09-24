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
    assert set(endpoint_hosts) >= set(services)
    services_with_no_endpoint = [service for service in services if len(endpoint_hosts[service]) == 0]
    # Services with no endpoint means they should probably go to the SERVICE_BLACKLIST
    assert not services_with_no_endpoint


def test_get_service_regions():
    services = get_services()
    regions = get_service_regions()
    assert set(regions) >= set(services)
    services_with_no_region = [service for service in services if len(regions[service]) == 0]
    # Services with no region means they should probably go to the SERVICE_BLACKLIST
    assert not services_with_no_region


def test_get_regions_for_service():
    requested_regions = ('us-east-2', 'eu-west-1', 'nonexistent')
    assert set(get_regions_for_service('ec2', requested_regions=requested_regions)) == set(('us-east-2', 'eu-west-1'))


def test_introspect_regions_for_service():
    introspect_regions_for_service()


def test_get_listing_operations():
    services_with_no_listings = set([
        service for service in get_services() if len(get_listing_operations(service, region='us-east-1')) == 0
    ])

    expected_no_listings = {
        'application-autoscaling',
        'budgets',
        'ce',
        'comprehendmedical',
        'connect',
        'ec2-instance-connect',
        'glacier',
        'health',
        'iot-data',
        'iot-jobs-data',
        'iotevents-data',
        'iotthingsgraph',
        'lex-runtime',
        'marketplace-entitlement',
        'marketplacecommerceanalytics',
        'mediaconvert',
        'meteringmarketplace',
        'personalize-events',
        'personalize-runtime',
        'pi',
        'pinpoint-sms-voice',
        'pricing',
        'quicksight',
        'rds-data',
        'resourcegroupstaggingapi',
        'sagemaker-runtime',
        'sts',
        'swf',
        'textract',
        'workdocs',
        'worklink',
    }

    assert expected_no_listings - services_with_no_listings == set(), 'Extra services gained listings, please check!'
    assert services_with_no_listings - expected_no_listings == set(), 'Some services have no listings, please check!'
