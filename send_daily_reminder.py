#!/usr/bin/env python
"""
Send a daily 8:00 AM CST reminder to download the RRC daf420 file.
Runs via Windows Task Scheduler.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
from pathlib import Path

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "daily_reminder.log"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)

# Email config from environment
smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
smtp_port = int(os.environ.get("SMTP_PORT", "587"))
smtp_user = os.environ.get("SMTP_USER", "mapmatics.gis@gmail.com")
smtp_password = os.environ.get("SMTP_PASSWORD")
recipient = os.environ.get("ALERT_TO_EMAIL", "mapmatics.gis@gmail.com")

if not smtp_password:
    logger.error("SMTP_PASSWORD not set in environment")
    exit(1)

# Create email
msg = MIMEMultipart("alternative")
msg["From"] = smtp_user
msg["To"] = recipient
msg["Subject"] = "REMINDER: Download RRC daf420 file (8:00 AM)"

# Email body
body = """Good morning!

It's 8:00 AM CST. Time to download today's RRC daf420 file.

STEPS:
1. Go to RRC GoDrive folder: https://drive.google.com/drive/folders/1wJ6k-R_IgbmxLg8LvBVFz7ZvBWRdEKJr
2. Download today's file: daf420.dat.MM-DD-YYYY
3. Either:
   a) Drop into: C:\\GIS\\permit_intel\\data\\tx\\inbox\\
      (auto-commits within 15 min)
   b) Upload via GitHub web UI:
      https://github.com/mapmaticsgis-maker/gis-permit-intel

GitHub Actions will run at 9:00 AM CST and send you the daily brief.

---
Automated reminder from permit-intel pipeline
"""

msg.attach(MIMEText(body, "plain"))

# Send
try:
    server = smtplib.SMTP(smtp_host, smtp_port)
    server.starttls()
    server.login(smtp_user, smtp_password)
    server.send_message(msg)
    server.quit()
    logger.info(f"[SUCCESS] Reminder sent to {recipient}")
except Exception as e:
    logger.error(f"[FAILED] Could not send reminder: {e}")
    exit(1)
