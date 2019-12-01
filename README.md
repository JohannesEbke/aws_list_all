# aws\_list\_all ![BuildTravis](https://travis-ci.org/JohannesEbke/aws_list_all.svg?branch=master "https://travis-ci.org/JohannesEbke/aws_list_all")

List all resources in an AWS account, all regions, all services(*). Writes JSON files for further processing.
Those JSON files can be converted to CSV files and merged in one XLSX (Excel workbook) file.

(*) No guarantees for completeness. Use billing alerts if you are worried about costs.

## Installation

### Basic mode
You need to have python (both 2 or 3 work) as well as AWS credentials set up as usual.

Quick Start with virtualenv (if you don't use python 3, change `python3` by your python version):

```shell script
$ mkvirtualenv -p $(which python3) aws
$ pip install aws-list-all
$ aws-list-all query --region eu-west-1 --service ec2 --directory ./data/
```

Quick Start Output:
```
Building set of queries to execute...
...done. Executing queries...
---------------------------------------------------------------...done
Here are the results...
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
```
Lines start with "``---``" if no resources of this type have been found, and
start with "``+++``" if at least one resource has been found.
"``>:|``" denotes an error due to missing permissions, other errors are prefixed with "``!!!``",

### Development mode

You may create a virtual environment and install dependencies:
```shell script
$ pipenv install -r requirements.txt
$ pipenv shell
```
To use it, replace `aws-list-all` by `./main.py` in the examples below.

### Information

Currently, some default resources are still considered "user-created" and thus listed,
this may change in the future.

Details about found resources are saved in json files named after the service,
region, and operation used to find them. They can be dumped with:

```shell script
$ aws-list-all show data/ec2/*.json
```
or 
```shell script
$ aws-list-all show --verbose data/ec2/Addresses_eu-west-3.json
```

**NOTE:** If you want a brief description about a command, use the `-h` or `--help` flag.

## How do I really list everything?

Warning: As AWS has over 1024 API endpoints, you may have to increase your allowed number of open files
See https://github.com/JohannesEbke/aws_list_all/issues/6

Restricting the region and service is optional, a simple ``query`` without arguments lists everything.
It uses a thread pool to parallelize queries and randomizes the order to avoid
hitting one endpoint in close succession. One run takes around two minutes for me.


## Examples

* Add immediate, more verbose output to a query with ``--verbose``. Use twice for even more verbosity:

```shell script
$ aws-list-all query --region eu-west-1 --service ec2 --operation DescribeVpcs --directory data --verbose
```

* Show resources for all returned queries:

```shell script
$ aws-list-all show --verbose data/*/*
```

* Show resources for all ec2 returned queries:

```shell script
$ aws-list-all show --verbose data/ec2/*.json
```

* List available services to query:

```shell script
$ aws-list-all introspect list-services
```

* List available operations for a given service, do:

```shell script
$ aws-list-all introspect list-operations --service ec2
```

* List all resources in sequence to avoid throttling:

```shell script
$ aws-list-all query --parallel 1
```

* Convert JSON files to `.csv` files and merge them into a `.xlsx` file:
```shell script
$ aws-list-all merge --verbose --directory ./data
```
**Note:** You an specify a session-name if you want to convert `.json` files only for a session.

### Cost explorer
There is a small script to retrieve some costs from a date to an another date. The costs aren't
detailed. The date format is: `YYYY-MM-DD`.
```shell script
$ ./cost_explorer.py --date-start 2018-01-01 --date-end 2019-01-10 --output-directory cost_explorer
```
