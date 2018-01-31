# aws_list_all

List all resources in an AWS account, all regions, all services(*).

(*) No guarantees for completeness. Use billing alerts if you are worried about costs.

[![Build Status](https://travis-ci.org/JohannesEbke/aws_list_all.svg?branch=master)](https://travis-ci.org/JohannesEbke/aws_list_all)

## Usage

You need to have python (both 2 or 3 work) with boto3 installed,
as well as AWS credentials which can be picked up by boto3.

To list resources for a given service and region, do
```
python -m aws_list_all --query --service ec2 --region eu-west-1
```
Example output:
```
--> ec2 eu-west-1 DescribeVolumeStatus VolumeStatuses
--- ec2 eu-west-1 DescribeVpcPeeringConnections VpcPeeringConnections
--- ec2 eu-west-1 DescribeExportTasks ExportTasks
--- ec2 eu-west-1 DescribePlacementGroups PlacementGroups
--- ec2 eu-west-1 DescribeSnapshots Snapshots
--- ec2 eu-west-1 DescribeConversionTasks ConversionTasks
--> ec2 eu-west-1 DescribeInternetGateways InternetGateways
--- ec2 eu-west-1 DescribeBundleTasks BundleTasks
--> ec2 eu-west-1 DescribeNetworkAcls NetworkAcls
....
```
Lines start with "---" if no resources of this type have been found, and
start with "-->" if at least one resource has been found.

Currently, some default resources are still considered "user-created", this may
change in the future.

Details about found resources are saved in pickle files named after the service,
region, and operation used to find them. They can be dumped with

```
python -m aws_list_all ec2_DescribeSecurityGroups_eu-west-1.pickle
```

## Enough of this, how do I really list everything?

Restricting the region and service is optional, a simple `--query` lists everything.
It uses a thread pool to parallelize queries and randomizes the order to avoid
hitting one endpoint in close succession. One run takes around two minutes for me.
