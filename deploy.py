"""
Deploy LocalStack demo resources:
  - S3 bucket (demo-bucket)
  - DynamoDB table (file-metadata)
  - Lambda function (file-processor) — triggered on S3 PUT
"""

import io
import json
import os
import time
import zipfile
import pathlib
import boto3
from botocore.exceptions import ClientError

BUCKET_NAME = "demo-bucket"
TABLE_NAME = "file-metadata"
FUNCTION_NAME = "file-processor"

# On LocalStack set LAMBDA_ROLE_ARN=arn:aws:iam::000000000000:role/lambda-role (any value works).
# On real AWS set it to an actual IAM role ARN with Lambda + S3 + DynamoDB permissions.
ROLE_ARN = os.environ["LAMBDA_ROLE_ARN"]

# ── helpers ────────────────────────────────────────────────────────────────────
# boto3 reads AWS_ENDPOINT_URL, AWS_DEFAULT_REGION, and credentials from the
# environment automatically.  Set them via .env.localstack or .env.aws before
# running this script — no hardcoded values here.

def client(service):
    return boto3.client(service)

def resource(service):
    return boto3.resource(service)

def zip_lambda() -> bytes:
    """Zip lambda/handler.py into an in-memory zip."""
    buf = io.BytesIO()
    handler_path = pathlib.Path(__file__).parent / "lambda" / "handler.py"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(handler_path, "handler.py")
    return buf.getvalue()


# ── resource creation ──────────────────────────────────────────────────────────

def create_bucket(s3):
    try:
        s3.create_bucket(Bucket=BUCKET_NAME)
        print(f"  ✓ S3 bucket created: {BUCKET_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"  ~ S3 bucket already exists: {BUCKET_NAME}")
        else:
            raise


def create_table(dynamodb):
    try:
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "file_key", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "file_key", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        # Wait until table is active
        waiter = dynamodb.get_waiter("table_exists")
        waiter.wait(TableName=TABLE_NAME)
        print(f"  ✓ DynamoDB table created: {TABLE_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"  ~ DynamoDB table already exists: {TABLE_NAME}")
        else:
            raise


def create_lambda(lmb):
    zip_bytes = zip_lambda()
    try:
        lmb.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.12",
            Role=ROLE_ARN,
            Handler="handler.handler",
            Code={"ZipFile": zip_bytes},
            Environment={"Variables": {"DYNAMODB_TABLE": TABLE_NAME}},
            Timeout=30,
        )
        print(f"  ✓ Lambda function created: {FUNCTION_NAME}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceConflictException":
            # Update existing function code
            lmb.update_function_code(FunctionName=FUNCTION_NAME, ZipFile=zip_bytes)
            print(f"  ~ Lambda function updated: {FUNCTION_NAME}")
        else:
            raise

    # Wait for function to be Active
    for _ in range(20):
        resp = lmb.get_function_configuration(FunctionName=FUNCTION_NAME)
        if resp["State"] == "Active":
            break
        time.sleep(1)

    return lmb.get_function(FunctionName=FUNCTION_NAME)["Configuration"]["FunctionArn"]


def add_s3_invoke_permission(lmb, function_arn):
    try:
        lmb.add_permission(
            FunctionName=FUNCTION_NAME,
            StatementId="s3-invoke",
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn=f"arn:aws:s3:::{BUCKET_NAME}",
        )
        print(f"  ✓ S3 invoke permission added to Lambda")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceConflictException":
            print(f"  ~ S3 invoke permission already exists")
        else:
            raise


def wire_s3_trigger(s3, function_arn):
    s3.put_bucket_notification_configuration(
        Bucket=BUCKET_NAME,
        NotificationConfiguration={
            "LambdaFunctionConfigurations": [
                {
                    "LambdaFunctionArn": function_arn,
                    "Events": ["s3:ObjectCreated:*"],
                }
            ]
        },
    )
    print(f"  ✓ S3 → Lambda trigger configured (s3:ObjectCreated:*)")


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    print("\n=== LocalStack Demo: Deploying resources ===\n")

    s3 = client("s3")
    dynamodb = client("dynamodb")
    lmb = client("lambda")

    print("[1/4] Creating S3 bucket...")
    create_bucket(s3)

    print("[2/4] Creating DynamoDB table...")
    create_table(dynamodb)

    print("[3/4] Creating Lambda function...")
    function_arn = create_lambda(lmb)

    print("[4/4] Wiring S3 → Lambda trigger...")
    add_s3_invoke_permission(lmb, function_arn)
    wire_s3_trigger(s3, function_arn)

    print("\n=== Deployment complete ===")
    print(f"  Bucket  : s3://{BUCKET_NAME}")
    print(f"  Table   : {TABLE_NAME}")
    print(f"  Lambda  : {FUNCTION_NAME}  ({function_arn})")
    print("\nRun  python3 test_upload.py  to upload a test file and verify the pipeline.\n")


if __name__ == "__main__":
    main()
