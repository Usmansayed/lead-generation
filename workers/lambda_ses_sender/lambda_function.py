"""
AWS Lambda: consume SQS messages (email jobs) and send via Amazon SES.
Configure: SQS trigger, env SES_FROM_EMAIL, SES_REGION. IAM: SES + SQS.
"""
import json
import os
import boto3


def lambda_handler(event, context):
    from_email = os.environ.get("SES_FROM_EMAIL", "")
    region = os.environ.get("SES_REGION", "us-east-1")
    if not from_email:
        return {"statusCode": 500, "body": "SES_FROM_EMAIL not set"}
    client = boto3.client("ses", region_name=region)
    ok, fail = 0, 0
    for record in event.get("Records", []):
        try:
            body = json.loads(record.get("body", "{}"))
            to_email = body.get("toEmail") or body.get("to_email")
            subject = body.get("subject", "")
            body_text = body.get("bodyText") or body.get("body_text", "")
            if not to_email:
                fail += 1
                continue
            client.send_email(
                Source=from_email,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": body_text, "Charset": "UTF-8"},
                    },
                },
            )
            ok += 1
        except Exception:
            fail += 1
    return {"ok": ok, "fail": fail}
