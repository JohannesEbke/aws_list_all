import json
import pprint

import boto3

from .client import get_client

class CountFilter:
    def __init__(self, complete):
        self.complete = complete

    def execute(self, listing, response):
        if 'Count' in response:
            if 'MaxResults' in response:
                if response['MaxResults'] <= response['Count']:
                    self.complete = False
                del response['MaxResults']
            del response['Count']

class QuantityFilter:
    def __init__(self, complete):
        self.complete = complete

    def execute(self, listing, response):
        if 'Quantity' in response:
            if 'MaxItems' in response:
                if response['MaxItems'] <= response['Quantity']:
                    self.complete = False
                del response['MaxItems']
            del response['Quantity']

class NeutralThingFilter:
    def execute(self, listing, response):
        for neutral_thing in ('MaxItems', 'MaxResults', 'Quantity'):
            if neutral_thing in response:
                del response[neutral_thing]

class BadThingFilter:
    def __init__(self, complete):
        self.complete = complete

    def execute(self, listing, response):
        for bad_thing in (
            'hasMoreResults', 'IsTruncated', 'Truncated', 'HasMoreApplications', 'HasMoreDeliveryStreams',
            'HasMoreStreams', 'NextToken', 'NextMarker', 'nextMarker', 'Marker'
        ):
            if bad_thing in response:
                if response[bad_thing]:
                    self.complete = False
                del response[bad_thing]

class NextTokenFilter:
    def __init__(self, complete):
        self.complete = complete

    def execute(self, listing, response):
        # interpret nextToken in several services
        if (listing.service, listing.operation) in (('inspector', 'ListFindings'), ('logs', 'DescribeLogGroups')):
            if response.get('nextToken'):
                self.complete = False
                del response['nextToken']