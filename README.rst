aws\_list\_all
==============

List all resources in an AWS account, all regions, all services(*). Writes JSON files for further processing.

(*) No guarantees for completeness. Use billing alerts if you are worried about costs.

.. image:: https://img.shields.io/pypi/v/aws-list-all
   :alt: PyPI

.. image:: https://github.com/JohannesEbke/aws_list_all/actions/workflows/tests.yaml/badge.svg
   :target: https://github.com/JohannesEbke/aws_list_all/actions/workflows/tests.yaml

Usage
-----

You need to have python (both 2 or 3 work) as well as AWS credentials set up as usual.

Quick Start with virtualenv::

  mkvirtualenv -p $(which python3) aws
  pip install aws-list-all
  aws-list-all query --region eu-west-1 --service ec2 --directory ./data/

Quick Start Output::

  ---------------8<--(snip)--8<-------------------
  --- ec2 eu-west-1 DescribeVolumes Volumes
  --- ec2 eu-west-1 DescribeVolumesModifications VolumesModifications
  --- ec2 eu-west-1 DescribeVpcEndpointConnectionNotifications ConnectionNotificationSet
  --- ec2 eu-west-1 DescribeVpcEndpointConnections VpcEndpointConnections
  --- ec2 eu-west-1 DescribeVpcEndpointServiceConfigurations ServiceConfigurations
  --- ec2 eu-west-1 DescribeVpcEndpoints VpcEndpoints
  --- ec2 eu-west-1 DescribeVpcPeeringConnections VpcPeeringConnections
  --- ec2 eu-west-1 DescribeVpcs Vpcs
  --- ec2 eu-west-1 DescribeVpnConnections VpnConnections
  --- ec2 eu-west-1 DescribeVpnGateways VpnGateways
  +++ ec2 eu-west-1 DescribeKeyPairs KeyPairs
  +++ ec2 eu-west-1 DescribeSecurityGroups SecurityGroups
  +++ ec2 eu-west-1 DescribeTags Tags
  !!! ec2 eu-west-1 DescribeClientVpnEndpoints ClientError('An error occurred (InternalError) when calling the DescribeClientVpnEndpoints operation (reached max retries: 4): An internal error has occurred')

Lines start with "``---``" if no resources of this type have been found, and
start with "``+++``" if at least one resource has been found.
"``>:|``" denotes an error due to missing permissions, other errors are prefixed with "``!!!``",

Currently, some default resources are still considered "user-created" and thus listed,
this may change in the future.

Details about found resources are saved in json files named after the service,
region, and operation used to find them. They can be dumped with::

  aws-list-all show data/ec2_*
  aws-list-all show --verbose data/ec2_DescribeSecurityGroups_eu-west-1.json

How do I really list everything?
------------------------------------------------

Warning: As AWS has over 1024 API endpoints, you may have to increase your allowed number of open files
See https://github.com/JohannesEbke/aws_list_all/issues/6

Restricting the region and service is optional, a simple ``query`` without arguments lists everything.
It uses a thread pool to parallelize queries and randomizes the order to avoid
hitting one endpoint in close succession. One run takes around two minutes for me.


More Examples
-------------

Add immediate, more verbose output to a query with ``--verbose``. Use twice for even more verbosity::

  aws-list-all query --region eu-west-1 --service ec2 --operation DescribeVpcs --directory data --verbose

Show resources for all returned queries::

  aws-list-all show --verbose data/*

Show resources for all ec2 returned queries::

  aws-list-all show --verbose data/ec2*

List available services to query::

  aws-list-all introspect list-services

List available operations for a given service, do::

  aws-list-all introspect list-operations --service ec2

List all resources in sequence to avoid throttling::

  aws-list-all query --parallel 1
