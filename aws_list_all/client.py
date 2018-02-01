import boto3

_CLIENTS = {}


def get_regions_for_service(service):
    """Given a service name, return a list of region names where this service can have resources"""
    if service == "s3":
        return ['us-east-1']  # s3 ListBuckets is a global request, so no region required.
    return boto3.Session().get_available_regions(service) or [None]


def get_client(service, region=None):
    """Return (cached) boto3 clients for this service and this region"""
    if not region:
        region = get_regions_for_service(service)[0]
    if (service, region) not in _CLIENTS:
        _CLIENTS[(service, region)] = boto3.Session(region_name=region).client(service)
    return _CLIENTS[(service, region)]
