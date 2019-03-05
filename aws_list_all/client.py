import boto3

_CLIENTS = {}


def get_regions_for_service(service, regions=()):
    """Given a service name, return a list of region names where this service can have resources,
    restricted by a possible set of regions."""
    # if service == "s3":
    #    return ['us-east-1']  # s3 ListBuckets is a global request, so no region required.
    # if service == "route53":
    #    return ['us-east-1']  # route53 is a global service, but the endpoint is in us-east-1.
    service_regions = boto3.Session().get_available_regions(service) or [None]
    if regions:
        # If regions were passed, return the intersecion.
        return [r for r in regions if r in service_regions]
    else:
        return service_regions


def get_client(service, region=None):
    """Return (cached) boto3 clients for this service and this region"""
    if (service, region) not in _CLIENTS:
        _CLIENTS[(service, region)] = boto3.Session(region_name=region).client(service)
    return _CLIENTS[(service, region)]
