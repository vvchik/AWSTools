#!/usr/bin/env python

#based on this https://gist.github.com/pet0ruk/4d26f3a919bc5f32816cbc705ee4ded3
#thich is based on this https://gist.github.com/miketheman/2630437

import boto3
import argparse


def lookup_by_id(sgid):
    sg = ec2.get_all_security_groups(group_ids=sgid)
    return sg[0].name


# get a full list of the available regions
client = boto3.client('ec2')
regions_dict = client.describe_regions()
region_list = [region['RegionName'] for region in regions_dict['Regions']]

# parse arguments
parser = argparse.ArgumentParser(description="Show unused security groups")
parser.add_argument("-r", "--region", type=str, default="us-east-1",
                    help="The default region is us-east-1. The list of available regions are as follows: %s" % sorted(
                        region_list))
parser.add_argument("-d", "--delete", help="delete security groups from AWS", action="store_true")
args = parser.parse_args()

client = boto3.client('ec2', region_name=args.region)
ec2 = boto3.resource('ec2', region_name=args.region)
all_groups = []
security_groups_in_use = []
# Get ALL security groups names
security_groups_dict = client.describe_security_groups()
security_groups = security_groups_dict['SecurityGroups']
security_groups_usage = {}
for groupobj in security_groups:
    all_groups.append(groupobj['GroupId'])
    security_groups_usage[groupobj['GroupId']] = {}
    security_groups_usage[groupobj['GroupId']]['SecurityGroupName'] = [groupobj['GroupName']]
    if groupobj['GroupName'] == 'default':
        security_groups_in_use.append(groupobj['GroupId'])

    


# Get all security groups used by instances
instances_dict = client.describe_instances()
reservations = instances_dict['Reservations']
network_interface_count = 0

for i in reservations:
    for j in i['Instances']:
        for k in j['SecurityGroups']:
            if k['GroupId'] not in security_groups_in_use:
                security_groups_in_use.append(k['GroupId'])
                security_groups_usage[k['GroupId']]['ec2id:'] = [j['InstanceId']]
            else:
                if 'ec2id:' in security_groups_usage[k['GroupId']]:
                    security_groups_usage[k['GroupId']]['ec2id:'].append(j['InstanceId'])
                else:
                    security_groups_usage[k['GroupId']]['ec2id:'] = [j['InstanceId']]

        # Security groups used by network interfaces
        for m in j['NetworkInterfaces']:
            network_interface_count += 1
            for n in m['Groups']:
                if n['GroupId'] not in security_groups_in_use:
                    security_groups_in_use.append(n['GroupId'])
                    security_groups_usage[n['GroupId']]['ec2if:'] = [m['NetworkInterfaceId']]
                else:
                    if 'ec2if:' in security_groups_usage[n['GroupId']]:
                        security_groups_usage[n['GroupId']]['ec2if:'].append(m['NetworkInterfaceId'])
                    else:
                        security_groups_usage[n['GroupId']]['ec2if:'] = [m['NetworkInterfaceId']]


# Security groups used by classic ELBs
elb_client = boto3.client('elb', region_name=args.region)
elb_dict = elb_client.describe_load_balancers()
for i in elb_dict['LoadBalancerDescriptions']:
    for j in i['SecurityGroups']:
        if j not in security_groups_in_use:
            security_groups_in_use.append(j)
            security_groups_usage[j]['ELBsg:'] = [i['LoadBalancerName']]
        else:
            if 'ELBsg:' in security_groups_usage[j]:
                security_groups_usage[j]['ELBsg:'].append(i['LoadBalancerName'])
            else:
                security_groups_usage[j]['ELBsg:'] = [i['LoadBalancerName']]

# Security groups used by ALBs
elb2_client = boto3.client('elbv2', region_name=args.region)
elb2_dict = elb2_client.describe_load_balancers()
for i in elb2_dict['LoadBalancers']:
    for j in i['SecurityGroups']:
        if j not in security_groups_in_use:
            security_groups_in_use.append(j)
            security_groups_usage[j]['ALBsg:'] = [i['LoadBalancerName']]
        else:
            if 'ALBsg:' in security_groups_usage[j]:
                security_groups_usage[j]['ALBsg:'].append(i['LoadBalancerName'])
            else:
                security_groups_usage[j]['ALBsg:'] = [i['LoadBalancerName']]



# Security groups used by RDS
rds_client = boto3.client('rds', region_name=args.region)
rds_sgdict = rds_client.describe_db_security_groups()
rds_insdict = rds_client.describe_db_instances()

for i in rds_sgdict['DBSecurityGroups']:
    for j in i['EC2SecurityGroups']:
        if j not in security_groups_in_use:
            security_groups_in_use.append(j)
            security_groups_usage[j]['RDS:'] = [i['DBInstanceIdentifier']]
        else:
            if 'RDS:' in security_groups_usage[j]:
                security_groups_usage[j]['RDS:'].append(i['DBInstanceIdentifier'])
            else:
                security_groups_usage[j]['RDS:'] = [i['DBInstanceIdentifier']]

for i in rds_insdict['DBInstances']:
    for j in i['VpcSecurityGroups']:
        if j['VpcSecurityGroupId'] not in security_groups_in_use:
            security_groups_in_use.append(j['VpcSecurityGroupId'])
            security_groups_usage[j['VpcSecurityGroupId']]['DBVPC:'] = [i['DBInstanceIdentifier']]
        else:
            if 'DBVPC:' in security_groups_usage[j['VpcSecurityGroupId']]:
                security_groups_usage[j['VpcSecurityGroupId']]['DBVPC:'].append(i['DBInstanceIdentifier'])
            else:
                security_groups_usage[j['VpcSecurityGroupId']]['DBVPC:'] = [i['DBInstanceIdentifier']]



# Security groups used by VPCs
#vpc_dict = client.describe_vpcs()
#for i in vpc_dict['Vpcs']:
#    vpc_id = i['VpcId']
#    vpc = ec2.Vpc(vpc_id)
#    for s in vpc.security_groups.all():
#        if s.group_id not in security_groups_in_use:
#            security_groups_in_use.append(s.group_id)
#            security_groups_usage[s.group_id]['VPC:'] = [vpc_id]
#        else:
#            if 'VPC:' in security_groups_usage[s.group_id]:
#                security_groups_usage[s.group_id]['VPC:'].append(vpc_id)
#            else:
#                security_groups_usage[s.group_id]['VPC:'] = [vpc_id]
#
delete_candidates = []
for group in all_groups:
    if group not in security_groups_in_use and not group.startswith('AWS-OpsWorks-'):
        delete_candidates.append(group)
        security_groups_usage[group]['inuse:'] = ['false']


if args.delete:
    print("We will now delete security groups identified to not be in use.")
    for group in delete_candidates:
        security_group = ec2.SecurityGroup(group)
        try:
            security_group.delete()
        except Exception as e:
            print(e)
            print("{0} requires manual remediation.".format(security_group.group_name))
else:
    print("The list of security groups to be removed is below.")
    print("Run this again with `-d` to remove them")
    for group in sorted(delete_candidates):
        print("   " + group)

print("---------------")
print("Activity Report")
print("---------------")

print(u"Total number of Security Groups evaluated: {0:d}".format(len(security_groups_in_use)))
print(u"Total number of EC2 Instances evaluated: {0:d}".format(len(reservations)))
print(u"Total number of Load Balancers evaluated: {0:d}".format(len(elb_dict['LoadBalancerDescriptions']) +
                                                                len(elb2_dict['LoadBalancers'])))
print(u"Total number of Network Interfaces evaluated: {0:d}".format(network_interface_count))
if args.delete:
    print(u"Total number of security groups deleted: {0:d}".format(len(delete_candidates)))
else:
    print(u"Total number of security groups targeted for removal: {0:d}".format(len(delete_candidates)))

print("------------")
print("Usage Report")
print("------------")
#print(security_groups_usage)
for group in security_groups_usage.keys():
    print(group, security_groups_usage[group]['SecurityGroupName'][0])
    for item in security_groups_usage[group].keys():
        if item != 'SecurityGroupName':
            if security_groups_usage[group][item]:
                i=0
                for name in security_groups_usage[group][item]:
                    if i == 0:
                        print("\t" + item, "\t\t" + name)
                        i = 1
                    else:
                        print("\t\t\t" + name)

#        print("\t\t" + security_groups_usage[group][item])
#print(security_groups_usage)

    # For each security group in the total list, if not in the "used" list, flag for deletion
    # If running with a "--delete" flag, delete the ones flagged.