import boto3

_CLIENTS = {}


def get_client(service, region=None, arn=None, session_name=None):
    """Return (cached) boto3 clients for this service and this region"""
    if arn is not None and session_name is not None:
        sts = boto3.Session(region_name=region).client('sts')
        credentials = sts.assume_role(RoleArn=arn, RoleSessionName=session_name)
        if (service, region) not in _CLIENTS:
            _CLIENTS[(service, region)] = boto3.Session(region_name=region,
                                                        aws_access_key_id=credentials["Credentials"]["AccessKeyId"],
                                                        aws_secret_access_key=credentials["Credentials"]["SecretAccessKey"],
                                                        aws_session_token=credentials["Credentials"]["SessionToken"]).client(service)

    elif (service, region) not in _CLIENTS:
        _CLIENTS[(service, region)] = boto3.Session(region_name=region).client(service)
    return _CLIENTS[(service, region)]
