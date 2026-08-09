import boto3
import questionary

# ------------------------------------------------------------
# Every resource we create gets these tags, so we can find
# them later and make sure we only touch things WE created.
# ------------------------------------------------------------
TAGS = {
    "CreatedBy": "platform-cli",
    "Owner": "Ilan",
}

MAX_RUNNING_INSTANCES = 2


def to_aws_tags(tag_dict):
    result = []
    for key in tag_dict:
        value = tag_dict[key]
        one_tag = {"Key": key, "Value": value}
        result.append(one_tag)
    return result


def is_cli_created(tag_list):
    found = False
    for tag in tag_list:
        tag_key = tag["Key"]
        tag_value = tag["Value"]
        if tag_key == "CreatedBy" and tag_value == "platform-cli":
            found = True
    return found


# ================================================================
# EC2
# ================================================================

def get_latest_ami(os_choice):
    ssm = boto3.client('ssm', region_name='us-east-1')

    if os_choice == "1":
        # Latest Amazon Linux 2023
        param_name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
    else:
        # Latest Ubuntu 22.04 LTS
        param_name = "/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id"

    response = ssm.get_parameter(Name=param_name)
    return response["Parameter"]["Value"]


def count_running_cli_instances():
    ec2 = boto3.client('ec2', region_name='us-east-1')

    response = ec2.describe_instances(
        Filters=[
            {"Name": "tag:CreatedBy", "Values": ["platform-cli"]},
            {"Name": "instance-state-name", "Values": ["running"]}
        ]
    )

    count = 0
    reservations = response["Reservations"]
    for reservation in reservations:
        instances = reservation["Instances"]
        for instance in instances:
            count = count + 1
    return count


def ec2_create():
    instance_type = input("Instance type (t3.micro or t2.small): ")

    if instance_type != "t3.micro" and instance_type != "t2.small":
        print("ERROR: instance type must be t3.micro or t2.small")
        return

    running_count = count_running_cli_instances()
    if running_count >= MAX_RUNNING_INSTANCES:
        print("ERROR: cannot create more instances. Cap of " + str(MAX_RUNNING_INSTANCES) + " running CLI instances reached.")
        return

    print("1. Amazon Linux (latest)")
    print("2. Ubuntu (latest)")
    os_choice = input("Choose OS: ")

    if os_choice != "1" and os_choice != "2":
        print("ERROR: choose 1 or 2")
        return

    ami_id = get_latest_ami(os_choice)
    print("Using AMI: " + ami_id)

    ec2 = boto3.client('ec2', region_name='us-east-1')

    result = ec2.run_instances(
        InstanceType=instance_type,
        MaxCount=1,
        MinCount=1,
        ImageId=ami_id,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": to_aws_tags(TAGS)
            }
        ]
    )

    instance_id = result["Instances"][0]["InstanceId"]
    print("SUCCESS: created instance " + instance_id)


def ec2_list():
    ec2 = boto3.client('ec2', region_name='us-east-1')

    response = ec2.describe_instances(
        Filters=[
            {"Name": "tag:CreatedBy", "Values": ["platform-cli"]}
        ]
    )

    reservations = response["Reservations"]

    for reservation in reservations:
        instances = reservation["Instances"]
        for instance in instances:
            instance_id = instance["InstanceId"]
            state = instance["State"]["Name"]
            instance_type = instance["InstanceType"]
            print(instance_id + " - " + state + " - " + instance_type)


def get_instance_tags(instance):
    if "Tags" in instance:
        return instance["Tags"]
    else:
        return []


def ec2_manage():
    ec2 = boto3.client('ec2', region_name='us-east-1')

    response = ec2.describe_instances(
        Filters=[
            {"Name": "tag:CreatedBy", "Values": ["platform-cli"]}
        ]
    )

    reservations = response["Reservations"]

    # Build a list of choices to show on screen
    choices = []
    for reservation in reservations:
        instances = reservation["Instances"]
        for instance in instances:
            instance_id = instance["InstanceId"]
            state = instance["State"]["Name"]
            label = instance_id + " (" + state + ")"
            choices.append(label)

    if len(choices) == 0:
        print("No CLI-created instances found.")
        return

    # Show the list, let user move up/down with arrow keys and press Enter
    selected = questionary.select(
        "Pick an instance:",
        choices=choices
    ).ask()

    # selected looks like "i-080abd90f54164ff3 (running)"
    # we only want the id part before the space
    parts = selected.split(" ")
    instance_id = parts[0]

    # Now ask what to do with it
    action = questionary.select(
        "What do you want to do?",
        choices=["start", "stop"]
    ).ask()

    instance_info = ec2.describe_instances(InstanceIds=[instance_id])
    instance = instance_info["Reservations"][0]["Instances"][0]
    tags = get_instance_tags(instance)

    if is_cli_created(tags) == False:
        print("FAILURE: this instance was not created by the CLI")
        return

    if action == "start":
        ec2.start_instances(InstanceIds=[instance_id])
        print("SUCCESS: starting " + instance_id)
    else:
        ec2.stop_instances(InstanceIds=[instance_id])
        print("SUCCESS: stopping " + instance_id)


# ================================================================
# S3
# ================================================================

def s3_create():
    bucket_name = input("Enter bucket name: ")
    bucket_name = bucket_name.strip()

    visibility = input("Public or private? (press Enter for private): ")
    visibility = visibility.strip()
    visibility = visibility.lower()

    if visibility == "":
        visibility = "private"

    if visibility != "public" and visibility != "private":
        print("ERROR: must be public or private")
        return

    if visibility == "public":
        answer = input("Are you sure? (yes/no): ")
        answer = answer.strip()
        answer = answer.lower()
        if answer != "yes":
            print("Cancelled.")
            return

    s3 = boto3.client('s3', region_name='us-east-1')

    try:
        s3.create_bucket(Bucket=bucket_name)
    except Exception:
        print("FAILURE: bucket name '" + bucket_name + "' is already taken. Try a different name.")
        return

    s3.put_bucket_tagging(
        Bucket=bucket_name,
        Tagging={"TagSet": to_aws_tags(TAGS)}
    )

    print("SUCCESS: created bucket " + bucket_name + " (" + visibility + ")")


def bucket_is_cli_created(bucket_name):
    s3 = boto3.client('s3', region_name='us-east-1')

    try:
        response = s3.get_bucket_tagging(Bucket=bucket_name)
        tag_list = response["TagSet"]
        return is_cli_created(tag_list)
    except Exception:
        return False


def s3_list():
    s3 = boto3.client('s3', region_name='us-east-1')

    response = s3.list_buckets()
    all_buckets = response["Buckets"]

    for bucket in all_buckets:
        bucket_name = bucket["Name"]
        if bucket_is_cli_created(bucket_name):
            print(bucket_name)


def s3_manage():
    s3 = boto3.client('s3', region_name='us-east-1')

    response = s3.list_buckets()
    all_buckets = response["Buckets"]

    # Build a list of only the CLI-created buckets
    choices = []
    for bucket in all_buckets:
        bucket_name = bucket["Name"]
        if bucket_is_cli_created(bucket_name):
            choices.append(bucket_name)

    if len(choices) == 0:
        print("No CLI-created buckets found.")
        return

    selected_bucket = questionary.select(
        "Pick a bucket:",
        choices=choices
    ).ask()

    action = questionary.select(
        "What do you want to do?",
        choices=["upload a file", "delete bucket"]
    ).ask()

    # Double check ownership before doing anything, just to be safe
    if bucket_is_cli_created(selected_bucket) == False:
        print("FAILURE: this bucket was not created by the CLI")
        return

    if action == "upload a file":
        file_path = input("Enter full path to file: ")
        file_path = file_path.strip()

        path_parts = file_path.split("/")
        file_name = path_parts[len(path_parts) - 1]

        try:
            s3.upload_file(file_path, selected_bucket, file_name)
            print("SUCCESS: uploaded " + file_name)
        except Exception:
            print("FAILURE: could not upload file. Check the file path is correct.")

    else:
        # delete bucket - need to empty it first, S3 won't delete a bucket with files in it
        objects = s3.list_objects_v2(Bucket=selected_bucket)

        if "Contents" in objects:
            files_in_bucket = objects["Contents"]
            for one_file in files_in_bucket:
                key = one_file["Key"]
                s3.delete_object(Bucket=selected_bucket, Key=key)

        try:
            s3.delete_bucket(Bucket=selected_bucket)
            print("SUCCESS: deleted bucket " + selected_bucket)
        except Exception as error:
            print("FAILURE: could not delete bucket")
            print(error)


# ================================================================
# ROUTE53
# ================================================================

def clean_zone_id(zone_id):
    parts = zone_id.split("/")
    return parts[len(parts) - 1]


def route53_create():
    domain_name = input("Enter domain name: ")

    route53 = boto3.client('route53')

    try:
        response = route53.create_hosted_zone(
            Name=domain_name,
            CallerReference=domain_name + "-platform-cli"
        )
    except Exception:
        print("FAILURE: could not create zone. It may already exist.")
        return

    zone_id = response["HostedZone"]["Id"]
    clean_id = clean_zone_id(zone_id)

    route53.change_tags_for_resource(
        ResourceType="hostedzone",
        ResourceId=clean_id,
        AddTags=to_aws_tags(TAGS)
    )

    print("SUCCESS: created zone " + domain_name + " (" + clean_id + ")")


def zone_is_cli_created(zone_id):
    route53 = boto3.client('route53')
    clean_id = clean_zone_id(zone_id)

    response = route53.list_tags_for_resource(
        ResourceType="hostedzone",
        ResourceId=clean_id
    )

    tag_list = response["ResourceTagSet"]["Tags"]
    return is_cli_created(tag_list)


def route53_manage_record():
    zone_id = input("Enter zone ID: ")

    if zone_is_cli_created(zone_id) == False:
        print("FAILURE: this zone was not created by the CLI")
        return

    action = input("create, update, or delete? ")

    if action != "create" and action != "update" and action != "delete":
        print("ERROR: action must be create, update, or delete")
        return

    route53 = boto3.client('route53')
    clean_id = clean_zone_id(zone_id)

    if action == "delete":
        record_name = input("Record name to delete (e.g. www.example.com): ")

        if record_name == "":
            print("ERROR: record name cannot be empty")
            return

        response = route53.list_resource_record_sets(
            HostedZoneId=clean_id,
            StartRecordName=record_name,
            MaxItems="1"
        )

        record_sets = response["ResourceRecordSets"]

        if len(record_sets) == 0:
            print("FAILURE: no record found with that name")
            return

        found_record = record_sets[0]
        found_name = found_record["Name"]
        found_type = found_record["Type"]

        if found_name != record_name and found_name != record_name + ".":
            print("FAILURE: no record found with that exact name")
            return

        if found_type == "NS" or found_type == "SOA":
            print("FAILURE: cannot delete the zone's built-in NS/SOA record")
            return

        ttl = found_record["TTL"]
        resource_records = found_record["ResourceRecords"]

        try:
            route53.change_resource_record_sets(
                HostedZoneId=clean_id,
                ChangeBatch={
                    "Changes": [
                        {
                            "Action": "DELETE",
                            "ResourceRecordSet": {
                                "Name": found_name,
                                "Type": found_type,
                                "TTL": ttl,
                                "ResourceRecords": resource_records
                            }
                        }
                    ]
                }
            )
            print("SUCCESS: deleted record " + found_name)
        except Exception as error:
            print("FAILURE: could not delete that record")
            print(error)

    else:
        record_name = input("Record name (e.g. www.example.com): ")
        record_type = input("Record type (e.g. A): ")
        value = input("Value (e.g. an IP address): ")

        if record_name == "" or record_type == "" or value == "":
            print("ERROR: record name, type, and value cannot be empty")
            return

        try:
            route53.change_resource_record_sets(
                HostedZoneId=clean_id,
                ChangeBatch={
                    "Changes": [
                        {
                            "Action": "UPSERT",
                            "ResourceRecordSet": {
                                "Name": record_name,
                                "Type": record_type,
                                "TTL": 300,
                                "ResourceRecords": [
                                    {"Value": value}
                                ]
                            }
                        }
                    ]
                }
            )
            print("SUCCESS: " + action + " record " + record_name)
        except Exception as error:
            print("FAILURE: could not " + action + " that record")
            print(error)


def route53_list():
    route53 = boto3.client('route53')

    response = route53.list_hosted_zones()
    all_zones = response["HostedZones"]

    for zone in all_zones:
        zone_id = zone["Id"]
        zone_name = zone["Name"]
        if zone_is_cli_created(zone_id):
            print(zone_name + " - " + zone_id)


def route53_manage():
    route53 = boto3.client('route53')

    response = route53.list_hosted_zones()
    all_zones = response["HostedZones"]

    # Build a list of only the CLI-created zones
    choices = []
    for zone in all_zones:
        zone_id = zone["Id"]
        zone_name = zone["Name"]
        if zone_is_cli_created(zone_id):
            label = zone_name + " (" + zone_id + ")"
            choices.append(label)

    if len(choices) == 0:
        print("No CLI-created zones found.")
        return

    selected = questionary.select(
        "Pick a zone:",
        choices=choices
    ).ask()

    # selected looks like "ilanhouse.com. (/hostedzone/Z0009...)"
    # we only want the part inside the parentheses
    open_paren_index = selected.index("(")
    zone_id = selected[open_paren_index + 1: len(selected) - 1]

    # Double check ownership before doing anything, just to be safe
    if zone_is_cli_created(zone_id) == False:
        print("FAILURE: this zone was not created by the CLI")
        return

    action = questionary.select(
        "What do you want to do?",
        choices=["create/update a record", "delete a record"]
    ).ask()

    clean_id = clean_zone_id(zone_id)

    if action == "delete a record":
        record_name = input("Record name to delete (e.g. www.example.com): ")
        record_name = record_name.strip()

        if record_name == "":
            print("ERROR: record name cannot be empty")
            return

        response = route53.list_resource_record_sets(
            HostedZoneId=clean_id,
            StartRecordName=record_name,
            MaxItems="1"
        )

        record_sets = response["ResourceRecordSets"]

        if len(record_sets) == 0:
            print("FAILURE: no record found with that name")
            return

        found_record = record_sets[0]
        found_name = found_record["Name"]
        found_type = found_record["Type"]

        if found_name != record_name and found_name != record_name + ".":
            print("FAILURE: no record found with that exact name")
            return

        if found_type == "NS" or found_type == "SOA":
            print("FAILURE: cannot delete the zone's built-in NS/SOA record")
            return

        ttl = found_record["TTL"]
        resource_records = found_record["ResourceRecords"]

        try:
            route53.change_resource_record_sets(
                HostedZoneId=clean_id,
                ChangeBatch={
                    "Changes": [
                        {
                            "Action": "DELETE",
                            "ResourceRecordSet": {
                                "Name": found_name,
                                "Type": found_type,
                                "TTL": ttl,
                                "ResourceRecords": resource_records
                            }
                        }
                    ]
                }
            )
            print("SUCCESS: deleted record " + found_name)
        except Exception as error:
            print("FAILURE: could not delete that record")
            print(error)

    else:
        record_name = input("Record name (e.g. www.example.com): ")
        record_type = input("Record type (e.g. A): ")
        value = input("Value (e.g. an IP address): ")

        record_name = record_name.strip()
        record_type = record_type.strip()
        value = value.strip()

        if record_name == "" or record_type == "" or value == "":
            print("ERROR: record name, type, and value cannot be empty")
            return

        try:
            route53.change_resource_record_sets(
                HostedZoneId=clean_id,
                ChangeBatch={
                    "Changes": [
                        {
                            "Action": "UPSERT",
                            "ResourceRecordSet": {
                                "Name": record_name,
                                "Type": record_type,
                                "TTL": 300,
                                "ResourceRecords": [
                                    {"Value": value}
                                ]
                            }
                        }
                    ]
                }
            )
            print("SUCCESS: saved record " + record_name)
        except Exception as error:
            print("FAILURE: could not save that record")
            print(error)


# ================================================================
# HELP
# ================================================================

def show_help():
    print("")
    print("---- Help ----")
    print("This tool lets you create and manage AWS EC2 instances, S3 buckets,")
    print("and Route53 DNS zones/records, using tags to track what it created.")
    print("")
    print("Tagging: every resource gets CreatedBy=platform-cli and Owner=" + TAGS["Owner"])
    print("The CLI will only start/stop/upload/manage resources that have")
    print("the CreatedBy=platform-cli tag.")
    print("")
    print("EC2 rules: only t3.micro or t2.small, max " + str(MAX_RUNNING_INSTANCES) + " running instances.")
    print("S3 rules: public buckets require typing 'yes' to confirm.")
    print("Route53 rules: records can only be managed on CLI-created zones.")


# ================================================================
# MAIN MENU
# ================================================================

while True:
    print("")
    print("---- Platform CLI ----")
    print("1. EC2 - create instance")
    print("2. EC2 - list instances")
    print("3. EC2 - manage instance (start/stop)")
    print("4. S3 - create bucket")
    print("5. S3 - manage bucket (upload/delete)")
    print("6. S3 - list buckets")
    print("7. Route53 - create zone")
    print("8. Route53 - manage record (create/update/delete)")
    print("9. Route53 - list zones")
    print("10. Help")
    print("0. Exit")

    choice = input("Choose an option: ")

    if choice == "1":
        ec2_create()
    elif choice == "2":
        ec2_list()
    elif choice == "3":
        ec2_manage()
    elif choice == "4":
        s3_create()
    elif choice == "5":
        s3_manage()
    elif choice == "6":
        s3_list()
    elif choice == "7":
        route53_create()
    elif choice == "8":
        route53_manage()
    elif choice == "9":
        route53_list()
    elif choice == "10":
        show_help()
    elif choice == "0":
        print("Goodbye!")
        break
    else:
        print("Invalid choice, try again.")