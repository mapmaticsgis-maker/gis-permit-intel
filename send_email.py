"""
Sends the daily brief or a failure alert via SMTP. Credentials come from
environment variables — in GitHub Actions that means repo Secrets, so
nothing sensitive lives in the repo itself.

Required env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
ALERT_TO_EMAIL. Gmail works with an App Password: smtp.gmail.com, 587.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _send(subject: str, body: str):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    to_addr = os.environ["ALERT_TO_EMAIL"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())


def send_daily_brief(body: str, run_date: str):
    _send(f"Permit Intel — {run_date}", body)


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
