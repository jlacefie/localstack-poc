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

---

## How I Used AI (Claude Code)

I used [Claude Code](https://claude.ai/code) (claude-sonnet-4-6) as the primary development tool throughout this exercise — from project scaffolding through debugging.

**What Claude Code did well:**
- Generated all three Python files (`handler.py`, `deploy.py`, `test_upload.py`) correctly on the first attempt — the pipeline worked end-to-end without manual debugging
- Correctly identified that boto3 natively reads `AWS_ENDPOINT_URL` from the environment (a non-obvious but important fact that most LocalStack tutorials skip)
- Wrote idempotent deployment logic — `make deploy` is safe to run multiple times without leaving the stack in a broken state
- Structured the Lambda function defensively (streaming S3 reads, UTF-8 error handling, `Records` iteration)

**What required explicit prompting / where it struggled:**
- **Default to hardcoded endpoints**: Claude's initial output hardcoded `endpoint_url="http://localhost:4566"` and `aws_access_key_id="test"` in every boto3 call. This works locally but produces code that can't point at real AWS without manual edits. Fixing it required me to explicitly ask for environment-agnostic code.
- **Assumed AWS CLI was installed**: Claude initially proposed an AWS CLI-based deployment workflow. The CLI wasn't installed, requiring a pivot to pure boto3 — which is actually cleaner, but Claude didn't discover this proactively.
- **No LocalStack-specific knowledge in context**: Claude treated LocalStack as a black box. It didn't know, for example, that LocalStack auto-injects `AWS_ENDPOINT_URL` into Lambda execution environments — I had to point that out.

---

## Concrete AI Failure Mode

**The hardcoded endpoint problem** — and why it happens.

Claude's first version of all three Python files included this pattern:

```python
boto3.client("s3", endpoint_url="http://localhost:4566", aws_access_key_id="test", aws_secret_access_key="test")
```

This is technically correct for LocalStack but architecturally wrong for portable code. The cause: LLMs are trained on LocalStack tutorials and Stack Overflow answers that show the endpoint URL explicitly (because historically LocalStack required it). The model reproduces this pattern by default, even though boto3 has supported `AWS_ENDPOINT_URL` as a native environment variable since 2022.

The risk is subtle: the code *works*, so there's no error to catch. The portability problem is silent — it only surfaces when someone tries to `source .env.aws && make deploy` and gets unexpected connection errors or, worse, accidentally hits real AWS from a LocalStack-config script.

**Why this matters for LocalStack's product**: AI-generated code will increasingly be the first path through LocalStack for new users. If the dominant training pattern produces non-portable code, it creates a hidden upgrade cost — LocalStack works locally, but the transition to prod requires a manual audit of AI-generated configuration. A first-class `localstack init` command that generates opinionated, portable project templates would preempt this problem.

---

## Issues Encountered

| Issue | Resolution |
|---|---|
| AWS CLI not installed | Pivoted from `awslocal` CLI to pure `boto3` — more Pythonic and no extra dependency |
| Python 3.9 boto3 deprecation warning | Cosmetic warning only; the code runs fine. Upgrade to Python 3.10+ to silence it |
| Lambda async execution gap | `test_upload.py` uses `time.sleep(4)` after S3 upload to wait for async Lambda invocation. In CI, replace with a retry loop for determinism |
| S3 invoke permission — silent failure | Without `add_permission(Principal="s3.amazonaws.com")`, S3 fires the event but Lambda silently rejects it — nothing errors. Added the permission step and documented the ordering dependency |
| LocalStack state is ephemeral | All resources (S3 buckets, DynamoDB tables, Lambda functions) are wiped every time LocalStack restarts. This caught us off guard when testing the Web UI — the Resource Browser was empty because we had restarted LocalStack mid-session. The fix is to always run `make deploy` at the start of a new session. For persistence across restarts, LocalStack supports [Cloud Pods](https://docs.localstack.cloud/user-guide/state-management/cloud-pods/) (Pro feature) to snapshot and restore state. |

---

## Enhancement Idea

**`localstack init` — opinionated, portable project scaffolding**

The biggest friction point in this exercise was that AI-generated LocalStack code defaults to hardcoded endpoints and fake credentials. The fix is straightforward in the code, but easy to miss and invisible in its failure mode.

LocalStack could ship a `localstack init` command that generates a project skeleton with:
- Environment variable-driven boto3 config (`.env.localstack` + `.env.aws` template) baked in from the start
- A `Makefile` (or equivalent) that sources the right env file per target
- A pre-flight check: `localstack validate-portability` that scans Python/TypeScript files and flags any hardcoded `localhost:4566` or `aws_access_key_id="test"` strings

This directly addresses the AI-era problem: when a developer (or AI agent) clones a LocalStack template, they start with patterns that work both locally and in prod, rather than patterns that require manual remediation before going live. It also gives LocalStack a natural onboarding moment to introduce the [LocalStack Cloud](https://app.localstack.cloud) ephemeral instances as the natural "staging" tier between local and prod.

---

## Reflection: Adoption & Commercial Implications

LocalStack's core value proposition — develop and test cloud applications locally before touching real AWS — maps cleanly onto a three-tier workflow: local (LocalStack) → staging (LocalStack Cloud ephemeral instances) → prod (real AWS). The hands-on exercise exposed both where this workflow is smooth and where it still has friction.

**Where the experience was strong:** LocalStack's emulation fidelity is high enough that the same boto3 code ran identically against LocalStack and would run against real AWS with only an env var change. The S3 → Lambda → DynamoDB event chain worked on the first deploy. The Web UI's Resource Browser is a meaningful productivity win over the AWS Console for local iteration.

**Where friction exists — and commercial implications:**

1. **The AI code generation gap**: AI tools default to LocalStack-specific code patterns (hardcoded endpoints, fake credentials). As AI-assisted development becomes the default onboarding path for new LocalStack users, this gap becomes a retention risk — developers hit LocalStack successfully, generate non-portable code, and discover the problem only when trying to ship. A `localstack init` template or a portability linter closes this gap and also creates a natural upsell to LocalStack Cloud for "staging-fidelity" testing.

2. **The permission model is invisible until it breaks**: The S3 → Lambda permission chain (`add_permission` + `put_bucket_notification_configuration`) requires two steps with a specific ordering dependency. Miss either and the pipeline silently does nothing. This is a real AWS quirk that LocalStack faithfully reproduces — but the debugging experience (check CloudWatch, check Lambda logs, realize the event never fired) is opaque. A LocalStack-specific diagnostic command — `localstack diagnose s3-trigger --bucket demo-bucket --function file-processor` — that checks all the wiring in one shot would meaningfully reduce time-to-first-success for new users.

3. **Agentic workflows amplify both the value and the friction**: An AI agent running LocalStack as a feedback loop for cloud infrastructure iteration is a compelling use case — deploy, test, observe, iterate, all locally with no cost or blast radius. But agents need structured, machine-readable feedback to close that loop. Today, LocalStack's error surfaces (CLI output, CloudWatch logs, HTTP error responses) are optimized for human reading. Making them structured and queryable (JSON error schemas, a diagnostic API, agent-friendly observability) is the unlock that makes LocalStack not just useful for AI-assisted development, but *essential* to it.
