# LocalStack Demo: S3 → Lambda → DynamoDB Pipeline

A hands-on demonstration of event-driven local AWS development using [LocalStack](https://localstack.cloud) — no real AWS account or credentials required.

---

## What This Demo Does

Uploading a file to a local S3 bucket automatically triggers a Lambda function that reads the file, extracts metadata (filename, size, content type, a text preview), and writes it to a DynamoDB table — all running locally inside LocalStack.

```
Upload file to S3
        │
        │  s3:ObjectCreated event
        ▼
Lambda (file-processor)
        │  reads object from S3
        │  writes metadata to DynamoDB
        ▼
DynamoDB (file-metadata)
  file_key | bucket | size | content_type | preview | processed_at
```

---

## Prerequisites

- **Docker** — runs the LocalStack emulator container ([install Docker](https://www.docker.com/get-started))
- **LocalStack CLI** — manages the container; pulls the Docker image automatically on first start
  ```bash
  pip install localstack
  # or
  brew install localstack
  ```
- **Python 3.9+** (3.10+ recommended)

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install boto3
```

> Re-activate the virtual environment any time you open a new terminal: `source .venv/bin/activate`

> **Why boto3?** LocalStack emulates AWS API endpoints — boto3 is the Python client that talks to those endpoints. When `AWS_ENDPOINT_URL` points to `http://localhost:4566`, every boto3 call goes to LocalStack instead of real AWS. No code changes required to switch environments.

---

## Project Structure

```
.
├── lambda/
│   └── handler.py        # Lambda function: reads from S3, writes metadata to DynamoDB
├── deploy.py             # Creates all AWS resources in LocalStack via boto3
├── test_upload.py        # Uploads a test file and verifies the DynamoDB output
├── Makefile              # Convenience commands: start, deploy, test, logs, stop
├── .env.localstack       # Environment variables for local development (safe to commit)
├── .env.aws              # Template for real AWS deployment (gitignored — add your values)
└── .gitignore
```

---

## Quickstart

> **Note:** LocalStack is ephemeral — all resources are wiped when the container stops. Run `make deploy` at the start of every new session before testing.

### 1. Clone and install dependencies

```bash
git clone https://github.com/YOUR_USERNAME/localstack-demo.git
cd localstack-demo
python3 -m venv .venv
source .venv/bin/activate
pip install boto3
```

### 2. Start LocalStack

```bash
make start
```

This starts LocalStack in Docker, then waits until the emulator is fully ready before returning.

### 3. (Optional) Open the LocalStack Web UI

Open [app.localstack.cloud](https://app.localstack.cloud) in your browser now — before deploying — so you can watch resources appear in the Resource Browser live as you run the next steps. See [Connecting to the Web UI](#connecting-to-the-web-ui) for first-time setup.

### 4. Deploy all AWS resources

```bash
make deploy
```

This creates (idempotently — safe to re-run):
- S3 bucket: `demo-bucket`
- DynamoDB table: `file-metadata`
- Lambda function: `file-processor` (Python 3.12, triggered on S3 object creation)
- S3 → Lambda event notification

If you have the Web UI open, navigate to **Resource Browser → S3** and **Resource Browser → DynamoDB** to confirm the resources were created.

### 5. Run the end-to-end test

```bash
make test
```

Uploads a test file to S3, waits for Lambda to execute, then queries DynamoDB to confirm metadata was written. Expected output:

```
[1] Uploading s3://demo-bucket/sample/hello.txt ...
    Uploaded 77 bytes
[2] Waiting 4 s for Lambda to process the event...
[3] Querying DynamoDB table 'file-metadata' for key 'sample/hello.txt'...

=== SUCCESS — Lambda wrote metadata to DynamoDB ===
  file_key     : sample/hello.txt
  bucket       : demo-bucket
  size         : 77 bytes
  content_type : text/plain
  processed_at : 2026-05-24T15:12:44.851676+00:00
  preview      : 'Hello from LocalStack! This file was uploaded to trigger the Lambda pipeline.'
```

### 6. Tail logs (optional)

```bash
make logs
```

### 7. Stop LocalStack

```bash
make stop
```

---

## Switching Between LocalStack and Real AWS

The code contains no hardcoded endpoints or credentials. Environment variables control which target boto3 talks to:

| Variable | LocalStack (`.env.localstack`) | Real AWS (`.env.aws`) |
|---|---|---|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | *(unset — boto3 uses real AWS)* |
| `AWS_ACCESS_KEY_ID` | `test` | from `~/.aws/credentials` (or set explicitly) |
| `AWS_SECRET_ACCESS_KEY` | `test` | from `~/.aws/credentials` (or set explicitly) |
| `AWS_DEFAULT_REGION` | `us-east-1` | your target region |
| `LAMBDA_ROLE_ARN` | any fake ARN | a real IAM execution role ARN |

```bash
# Local development
source .env.localstack && make deploy && make test

# Real AWS (fill in .env.aws first)
source .env.aws && make deploy && make test
```

The Makefile defaults to `.env.localstack` but accepts an override:

```bash
make deploy ENV=.env.aws
```

---

## Connecting to the Web UI

The [LocalStack Web UI](https://app.localstack.cloud) lets you browse S3 buckets, DynamoDB tables, Lambda functions, and more without using the CLI. Do this setup once before your first `make deploy`.

1. Create a free account at [app.localstack.cloud](https://app.localstack.cloud)
2. Go to **Workspace → Auth Tokens** and copy your Developer Auth Token
3. Register it with the LocalStack CLI:
   ```bash
   localstack auth set-token <YOUR_AUTH_TOKEN>
   ```
4. Restart LocalStack so it starts authenticated:
   ```bash
   make stop
   make start
   ```
5. Your instance appears in the Web UI — then run `make deploy` and `make test` to see resources and data populate in real time

> Keep your auth token out of source control — never commit it or add it to `.env.localstack`.
