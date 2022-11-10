import boto3

_CLIENTS = {}


def get_client(service, region=None, profile=None):
    """Return (cached) boto3 clients for this service and this region"""
    key = (service, region, profile)
    if key not in _CLIENTS:
        _CLIENTS[key] = boto3.Session(region_name=region, profile_name=profile).client(service)
    return _CLIENTS[key]
