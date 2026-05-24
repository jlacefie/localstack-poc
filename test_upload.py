"""
Upload a test file to demo-bucket and verify Lambda wrote metadata to DynamoDB.
"""

import sys
import time
import boto3
# boto3 reads AWS_ENDPOINT_URL, region, and credentials from the environment.
# Source .env.localstack for LocalStack or .env.aws for real AWS before running.

BUCKET_NAME = "demo-bucket"
TABLE_NAME = "file-metadata"
TEST_KEY = "sample/hello.txt"
TEST_CONTENT = b"Hello from LocalStack! This file was uploaded to trigger the Lambda pipeline."


def client(service):
    return boto3.client(service)

def resource(service):
    return boto3.resource(service)


def main():
    s3 = client("s3")
    dynamodb = resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)

    print(f"\n[1] Uploading s3://{BUCKET_NAME}/{TEST_KEY} ...")
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=TEST_KEY,
        Body=TEST_CONTENT,
        ContentType="text/plain",
    )
    print(f"    Uploaded {len(TEST_CONTENT)} bytes")

    # Give Lambda a moment to execute asynchronously
    print("[2] Waiting 4 s for Lambda to process the event...")
    time.sleep(4)

    print(f"[3] Querying DynamoDB table '{TABLE_NAME}' for key '{TEST_KEY}'...")
    resp = table.get_item(Key={"file_key": TEST_KEY})
    item = resp.get("Item")

    if item:
        print("\n=== SUCCESS — Lambda wrote metadata to DynamoDB ===")
        print(f"  file_key     : {item.get('file_key')}")
        print(f"  bucket       : {item.get('bucket')}")
        print(f"  size         : {item.get('size')} bytes")
        print(f"  content_type : {item.get('content_type')}")
        print(f"  processed_at : {item.get('processed_at')}")
        print(f"  preview      : {item.get('preview', '')[:80]!r}")
    else:
        print("\n=== FAIL — No item found in DynamoDB ===")
        print("    Lambda may not have run yet. Check LocalStack logs:")
        print("    localstack logs")
        sys.exit(1)


if __name__ == "__main__":
    main()
