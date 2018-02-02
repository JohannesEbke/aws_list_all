import pprint

import boto3

from .client import get_client

PARAMETERS = {
    'ec2': {
        'DescribeSnapshots': {
            'OwnerIds': ['self']
        },
        'DescribeImages': {
            'Owners': ['self']
        },
    },
    'elasticbeanstalk': {
        'ListPlatformVersions': {
            'Filters': [{
                'Operator': '=',
                'Type': 'PlatformOwner',
                'Values': ['self']
            }]
        }
    },
    'iam': {
        'ListPolicies': {
            'Scope': 'Local'
        },
    },
    'ssm': {
        'ListDocuments': {
            'DocumentFilterList': [{
                'key': 'Owner',
                'value': 'self'
            }]
        },
    },
}

ssf = list(
    boto3.Session(
        region_name="us-east-1"
    ).client("cloudformation").meta.service_model.shape_for("ListStacksInput").members["StackStatusFilter"].member.enum
)
ssf.remove("DELETE_COMPLETE")
PARAMETERS.setdefault("cloudformation", {})["ListStacks"] = {"StackStatusFilter": ssf}


def run_raw_listing_operation(service, region, operation):
    """Execute a given operation and return its raw result"""
    client = get_client(service, region)
    api_to_method_mapping = dict((v, k) for k, v in client.meta.method_to_api_mapping.items())
    parameters = PARAMETERS.get(service, {}).get(operation, {})
    return getattr(client, api_to_method_mapping[operation])(**parameters)


class Listing(object):
    """Represents a listing operation on an AWS service and its result"""

    def __init__(self, service, region, operation, response):
        self.service = service
        self.region = region
        self.operation = operation
        self.response = response

    def to_json(self):
        return {
            'service': self.service,
            'region': self.region,
            'operation': self.operation,
            'response': self.response,
        }

    @classmethod
    def from_json(cls, data):
        return cls(
            service=data.get('service'),
            region=data.get('region'),
            operation=data.get('operation'),
            response=data.get('response')
        )

    @property
    def resource_types(self):
        """The list of resource types (Keys with list content) in the response"""
        return list(self.resources.keys())

    @property
    def resource_total_count(self):
        """The estimated total count of resources - can be incomplete"""
        return sum(len(v) for v in self.resources.values())

    def export_resources(self, filename):
        """Export the result to the given JSON file"""
        with open(filename, "w") as outfile:
            outfile.write(pprint.pformat(self.resources).encode('utf-8'))

    def __str__(self):
        opdesc = '{} {} {}'.format(self.service, self.region, self.operation)
        if len(self.resource_types) == 0 or self.resource_total_count == 0:
            return "{} (no resources found)".format(opdesc)
        return opdesc + ', '.join('#{}: {}'.format(key, len(listing)) for key, listing in self.resources.items())

    @classmethod
    def acquire(cls, service, region, operation):
        """Acquire the given listing by making an AWS request"""
        response = run_raw_listing_operation(service, region, operation)
        if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            raise Exception("Bad AWS HTTP Status Code", response)
        return cls(service, region, operation, response)

    @property
    def resources(self):  # pylint:disable=too-many-branches
        """Transform the response data into a dict of resource names to resource listings"""
        response = self.response.copy()
        complete = True

        del response["ResponseMetadata"]

        # Transmogrify strange cloudfront results into standard AWS format
        if self.service == "cloudfront" and self.operation in [
            "ListCloudFrontOriginAccessIdentities", "ListDistributions", "ListStreamingDistributions"
        ]:
            key = list(response.keys())[0][:-len("List")]
            response = list(response.values())[0]
            response[key] = response.get("Items", [])

        # SNS ListSubscriptions always sends a next token...
        if self.service == "sns" and self.operation == "ListSubscriptions":
            del response["NextToken"]

        if "Count" in response:
            if "MaxResults" in response:
                if response["MaxResults"] <= response["Count"]:
                    complete = False
                del response["MaxResults"]
            del response["Count"]

        if "MaxItems" in response:
            del response["MaxItems"]

        if "Quantity" in response:
            del response["Quantity"]

        for bad_thing in (
            "hasMoreResults", "IsTruncated", "Truncated", "HasMoreApplications", "HasMoreDeliveryStreams",
            "HasMoreStreams", "NextToken", "NextMarker", "Marker"
        ):
            if bad_thing in response:
                if response[bad_thing]:
                    complete = False
                del response[bad_thing]

        # Special handling for Aliases in kms, there are some reserved AWS-managed aliases.
        if self.service == "kms" and self.operation == "ListAliases":
            response["Aliases"] = [
                alias for alias in response.get("Aliases", [])
                if not alias.get("AliasName").lower().startswith("alias/aws")
            ]

        # Filter PUBLIC images from appstream
        if self.service == "appstream" and self.operation == "DescribeImages":
            response["Images"] = [
                image for image in response.get("Images", []) if not image.get("Visibility", "PRIVATE") == "PUBLIC"
            ]

        # This API returns a dict instead of a list
        if self.service == 'cloudsearch' and self.operation == 'ListDomainNames':
            response["DomainNames"] = list(response["DomainNames"].items())

        # Remove AWS supplied policies
        if self.service == "iam" and self.operation == "ListPolicies":
            response["Policies"] = [
                policy for policy in response["Policies"] if not policy['Arn'].startswith('arn:aws:iam::aws:')
            ]

        # Owner Info is not necessary
        if self.service == "s3" and self.operation == "ListBuckets":
            del response["Owner"]

        # Remove failures from ecs/DescribeClusters
        if self.service == 'ecs' and self.operation == 'DescribeClusters':
            if 'failures' in response:
                del response['failures']

        # Remove default Baseline
        if self.service == "ssm" and self.operation == "DescribePatchBaselines":
            response["BaselineIdentities"] = [
                line for line in response["BaselineIdentities"] if line['BaselineName'] != 'AWS-DefaultPatchBaseline'
            ]

        # Remove default DB Security Group
        if self.service == "rds" and self.operation == "DescribeDBSecurityGroups":
            response["DBSecurityGroups"] = [
                group for group in response["DBSecurityGroups"] if group['DBSecurityGroupName'] != 'default'
            ]

        # Filter default VPCs
        if self.service == "ec2" and self.operation == "DescribeVpcs":
            response["Vpcs"] = [vpc for vpc in response["Vpcs"] if not vpc["IsDefault"]]

        # Filter default Subnets
        if self.service == "ec2" and self.operation == "DescribeSubnets":
            response["Subnets"] = [net for net in response["Subnets"] if not net["DefaultForAz"]]

        # Filter default SGs
        if self.service == "ec2" and self.operation == "DescribeSecurityGroups":
            response["SecurityGroups"] = [sg for sg in response["SecurityGroups"] if sg["GroupName"] != "default"]

        # Filter main route tables
        if self.service == "ec2" and self.operation == "DescribeRouteTables":
            response["RouteTables"] = [
                rt for rt in response["RouteTables"] if not any(x["Main"] for x in rt["Associations"])
            ]

        # Filter default Network ACLs
        if self.service == "ec2" and self.operation == "DescribeNetworkAcls":
            response["NetworkAcls"] = [nacl for nacl in response["NetworkAcls"] if not nacl["IsDefault"]]

        for key, value in response.items():
            if not isinstance(value, list):
                raise Exception("No listing:", response)

        if not complete:
            response['truncated'] = [True]

        return response
