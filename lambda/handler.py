import json
import os
import boto3  # endpoint_url resolved via AWS_ENDPOINT_URL env var
from datetime import datetime, timezone


TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "file-metadata")


def handler(event, context):
    # boto3 reads AWS_ENDPOINT_URL from the environment automatically.
    # LocalStack injects it so the function talks back to LocalStack.
    # On real AWS the var is absent and boto3 uses standard AWS endpoints.
    s3 = boto3.client("s3")
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)

    results = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        size = record["s3"]["object"]["size"]

        obj = s3.get_object(Bucket=bucket, Key=key)
        content_type = obj.get("ContentType", "application/octet-stream")
        # Read up to 256 bytes for a content preview
        preview = obj["Body"].read(256).decode("utf-8", errors="replace")

        item = {
            "file_key": key,
            "bucket": bucket,
            "size": size,
            "content_type": content_type,
            "preview": preview,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        table.put_item(Item=item)
        results.append(item)
        print(f"Stored metadata for s3://{bucket}/{key} ({size} bytes)")

    return {
        "statusCode": 200,
        "body": json.dumps({"processed": len(results), "items": results}, default=str),
    }
