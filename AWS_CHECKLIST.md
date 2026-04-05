# AWS Console Checklist — Lead Generation Platform

Do these in the AWS Console **after** the codebase is ready. Order matters for dependencies.

---

## 1. Amazon SES (Email Sending)

- [ ] **Verify your sending domain**
  - SES → Verified identities → Create identity → Domain.
  - Enter your domain (e.g. `yourcompany.com`). Add the DNS records SES shows (CNAME for DKIM, TXT if any).
- [ ] **Verify sender email (optional for testing)**
  - Create identity → Email address. Use for testing in sandbox.
- [ ] **Request production access (move out of sandbox)**
  - Account dashboard → Request production access. Fill the form (use case: transactional/outreach, volume estimate).
- [ ] **Configure DNS for deliverability**
  - **SPF:** Add TXT record as recommended by SES (e.g. `v=spf1 include:amazonses.com ~all`).
  - **DKIM:** SES gives CNAME records; add them to your DNS.
  - **DMARC:** Add TXT `_dmarc.yourdomain.com` (e.g. `v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com`). Later move to `p=quarantine` or `p=reject`.
- [ ] **Warm-up**
  - Start with low volume (e.g. 20/day), increase gradually. Keep complaint rate < 0.1%, bounce < 2%.

---

## 2. Amazon SQS (Email Queue)

- [ ] **Create queue**
  - SQS → Create queue. Name e.g. `lead-gen-email-queue`.
  - Type: Standard (or FIFO if you need strict order).
  - Visibility timeout: e.g. 60 seconds (≥ Lambda timeout).
  - Message retention: 4 days (default).
- [ ] **Note the queue URL** — You will use it in Lambda env or config.

---

## 3. AWS Lambda (Email Worker)

- [ ] **Create function**
  - Lambda → Create function. Name e.g. `lead-gen-ses-sender`.
  - Runtime: Python 3.11+ (or Node).
  - Create new role with basic Lambda permissions.
- [ ] **Add permissions**
  - Role: add **AmazonSESFullAccess** (or minimal: `ses:SendEmail`, `ses:SendRawEmail`).
  - Role: add **AmazonSQSFullAccess** (or minimal: read/delete message on your queue).
- [ ] **Trigger**
  - Add trigger: SQS → select your `lead-gen-email-queue`. Batch size 1–10.
- [ ] **Environment variables**
  - `SES_FROM_EMAIL` (e.g. `outreach@yourdomain.com`)
  - `SES_REGION` (e.g. `us-east-1`)
  - Optionally: `MONGODB_URI` if Lambda updates lead status after send.
- [ ] **Code**
  - Deploy the worker that: receives SQS message (leadId, toEmail, subject, bodyText), calls `boto3.client('ses').send_email()`, then deletes message from SQS. Optionally update MongoDB `email_queue` and `raw_posts` status.

---

## 4. Amazon SNS (Bounce & Complaint)

- [ ] **Create SNS topic (optional but recommended)**
  - SNS → Topics → Create. Name e.g. `ses-bounces-complaints`.
- [ ] **SES → Configuration set**
  - SES → Configuration sets → Create. Name e.g. `lead-gen-events`.
  - Add event destination: Event type = Bounce, Complaint (and optionally Send, Delivery). Destination = SNS topic above.
- [ ] **Subscribe to topic**
  - SNS → Subscribe: Protocol = HTTPS (or Lambda) with your endpoint that marks lead as invalid / adds to suppression list and updates MongoDB.

---

## 5. IAM & Secrets

- [ ] **Secrets Manager (optional)**
  - Store `MONGODB_URI`, `APIFY_TOKEN`, and Bedrock config (`AWS_BEDROCK_API` or `AWS2_*`/`CLAUDE_*`) if you run pipeline from EC2/ECS/Lambda. Grant Lambda/EC2 role read access.
- [ ] **No hardcoded keys** — Use env vars or Secrets Manager in code.

---

## 6. CloudWatch (Monitoring)

- [ ] **Alarms**
  - SES: bounce rate > 2% or complaint rate > 0.1% → alarm.
  - SQS: dead-letter queue (create DLQ and point failed messages) → alarm on message count.
- [ ] **Logs**
  - Lambda logs go to CloudWatch Logs by default. Retention: set to 7–30 days.

---

## 7. Summary Table

| Service   | What you do |
|----------|--------------|
| **SES**  | Verify domain, DKIM/SPF/DMARC, request production, warm up. |
| **SQS**  | Create queue for email jobs; note URL. |
| **Lambda** | Create function, attach SQS trigger, add SES + SQS permissions, set env (SES_FROM_EMAIL, etc.), deploy sender code. |
| **SNS**  | Topic for bounces/complaints; link to SES config set; subscribe endpoint to update suppression list. |
| **CloudWatch** | Alarms on bounce/complaint and DLQ. |

After this, the pipeline can push email jobs to SQS (or MongoDB `email_queue`), and Lambda will send via SES and handle bounces/complaints via SNS.
