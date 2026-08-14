"""
Sends the daily brief or a failure alert via SMTP. Credentials come from
environment variables — in GitHub Actions that means repo Secrets, so
nothing sensitive lives in the repo itself.

Required env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
ALERT_TO_EMAIL. Gmail works with an App Password: smtp.gmail.com, 587.
"""
import mimetypes
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email import encoders
from pathlib import Path


def _send(subject: str, body: str, attachments: list | None = None):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    to_addr = os.environ["ALERT_TO_EMAIL"]

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.attach(MIMEText(body, "plain"))

    for path in attachments or []:
        path = Path(path)
        ctype, _ = mimetypes.guess_type(path.name)
        maintype, subtype = (ctype.split("/", 1) if ctype else ("application", "octet-stream"))
        part = MIMEBase(maintype, subtype)
        part.set_payload(path.read_bytes())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=path.name)
        msg.attach(part)

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())


def send_daily_brief(body: str, run_date: str, attachments: list | None = None):
    _send(f"Permit Intel — {run_date}", body, attachments)


def send_failure_alert(failed_checks: list, run_date: str, extra: str = ""):
    """Distinct subject line from the daily brief on purpose, so a broken
    run never gets mistaken for a quiet day."""
    lines = ["The daily permit intel run completed with failed self-checks:\n"]
    for name, ok, detail in failed_checks:
        if not ok:
            lines.append(f"- FAIL: {name} — {detail}")
    if extra:
        lines.append(f"\n{extra}")
    lines.append("\nCheck the Actions tab / run_log.csv for history.")
    _send(f"\u26a0 PERMIT INTEL PIPELINE ALERT — {run_date}", "\n".join(lines))
