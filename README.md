# 🚀 Platform CLI

A self-service command-line tool for provisioning **EC2**, **S3**, and **Route53** resources on AWS — built as a lightweight platform engineering layer so developers can request infrastructure within safe, pre-defined guardrails.

Every resource created by this tool is tagged, tracked, and scoped — the CLI will only ever start, stop, upload to, or delete resources it created itself.

---

## ✨ What it does

| Resource | Actions |
|---|---|
| 🖥️ **EC2** | Create (with instance type + running-instance cap enforced), list, start/stop |
| 🪣 **S3** | Create (public/private with confirmation), list, upload files, delete |
| 🌐 **Route53** | Create DNS zones, list, create/update/delete records |

All actions are driven by a simple interactive menu — arrow keys to pick resources, type to fill in the rest.

---

## 🛡️ Guardrails built in

- ✅ EC2 instance type limited to `t3.micro` or `t2.small`
- ✅ Hard cap of **2 running instances** created by this tool
- ✅ Latest **Ubuntu** or **Amazon Linux** AMI, looked up live via SSM
- ✅ S3 buckets default to **private**; going public requires typing `yes` to confirm
- ✅ Every action double-checks tags before touching a resource — nothing outside the tool's own resources is ever modified
- ✅ Route53's built-in `NS`/`SOA` records are protected from deletion

---

## 📋 Prerequisites

- Python 3.8+
- An AWS account with an IAM user/role that has permissions for EC2, S3, Route53, and SSM
- AWS CLI configured locally (`aws configure`) — this tool uses your existing AWS profile, **no credentials are stored in the code**

---

## ⚙️ Installation

```bash
git clone https://github.com/yourusername/aws-platform-cli.git
cd aws-platform-cli
pip install -r requirements.txt
```

---

## ▶️ Usage

```bash
python main.py
```

You'll see a menu like this:

```
---- Platform CLI ----
1. EC2 - create instance
2. EC2 - list instances
3. EC2 - manage instance (start/stop)
4. S3 - create bucket
5. S3 - manage bucket (upload/delete)
6. S3 - list buckets
7. Route53 - create zone
8. Route53 - manage record (create/update/delete)
9. Route53 - list zones
10. Help
0. Exit
```

Just type a number and follow the prompts.

### Example: create an EC2 instance

```
Choose an option: 1
Instance type (t3.micro or t2.small): t3.micro
1. Amazon Linux (latest)
2. Ubuntu (latest)
Choose OS: 2
Using AMI: ami-0abcd1234efgh5678
SUCCESS: created instance i-0123456789abcdef0
```

### Example: create a private S3 bucket

```
Choose an option: 4
Enter bucket name: myname-test-bucket-482
Public or private? (press Enter for private): [Enter]
SUCCESS: created bucket myname-test-bucket-482 (private)
```

### Example: create a DNS zone and record

```
Choose an option: 7
Enter domain name: mytestdomain.com
SUCCESS: created zone mytestdomain.com (Z00090423KKOVZCDOP2K8)

Choose an option: 8
Pick a zone: mytestdomain.com. (/hostedzone/Z00090423KKOVZCDOP2K8)
What do you want to do? create/update a record
Record name: www.mytestdomain.com
Record type: A
Value: 1.2.3.4
SUCCESS: saved record www.mytestdomain.com
```

---

## 🏷️ Tagging convention

Every resource created by this tool receives:

| Key | Value |
|---|---|
| `CreatedBy` | `platform-cli` |
| `Owner` | your name (set in `TAGS` at the top of `main.py`) |

The CLI checks for `CreatedBy=platform-cli` before allowing any start/stop/upload/delete/update action — resources without this tag are always refused.

---

## 🧹 Cleanup instructions

To avoid ongoing AWS charges, clean up test resources when you're done:

```bash
# EC2 — stop then terminate
aws ec2 terminate-instances --instance-ids i-xxxxxxxxxxxxx

# S3 — empty then delete (or use option 5 in the CLI, which does both)
aws s3 rm s3://your-bucket-name --recursive
aws s3api delete-bucket --bucket your-bucket-name

# Route53 — delete records first, then the zone
aws route53 delete-hosted-zone --id Z00000000000
```

> ⚠️ Route53 hosted zones incur a small monthly charge even when empty — don't leave test zones running.

---

## 🔒 Security

- No AWS credentials are hardcoded anywhere in this repo
- boto3 automatically uses your local AWS CLI profile
- `.gitignore` excludes `.aws/`, `*.pem`, and `*.env` files from ever being committed

---

## 🗂️ Project structure

```
aws-platform-cli/
├── main.py           # the whole CLI
├── requirements.txt  # boto3 + questionary
├── .gitignore
└── README.md
```
