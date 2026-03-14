import requests
import json
import smtplib
from email.mime.text import MIMEText

# -----------------------------
# CONFIGURATION
# -----------------------------

# Ollama LLM
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"

# Jira
JIRA_URL = "<JIRA URL>"
JIRA_EMAIL = "<JIRA EMAIL>"
JIRA_API_TOKEN = "<JIRA API TOKEN>"
JIRA_PROJECT_KEY = "SCRUM"

# Email
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "<EMAIL USER>"
EMAIL_PASS = "<EMAIL PASSWORD>"  # For Gmail, use App Password
EMAIL_TO = "<TO EMAIL>"

# Slack
SLACK_WEBHOOK = "<SLACK WEBHOOK URL>"

# -----------------------------
# LLM ANALYSIS
# -----------------------------

def analyze_problem(problem):

    prompt = f"""
You are an AI Helpdesk Agent.

Analyze the problem and return JSON with:

priority: Low, Medium, High
issue_type: Bug, Task, Story
needs_slack: true/false
needs_email: true/false

Problem:
{problem}

Return only JSON.
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }
    )

    result = response.json()["response"]

    return json.loads(result)

# -----------------------------
# CREATE JIRA TICKET
# -----------------------------

def create_jira_ticket(summary, priority, issue_type):

    url = f"{JIRA_URL}/rest/api/3/issue"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    summary = summary[:50]
    payload = {
        "fields": {
            "project": {
                "key": JIRA_PROJECT_KEY
            },
            "summary": summary,
            "issuetype": {
                "name": issue_type
            },
            "priority": {
                "name": priority
            },
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "text": summary,
                                "type": "text"
                            }
                        ]
                    }
                ]
            }
        }
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        auth=(JIRA_EMAIL, JIRA_API_TOKEN)
    )

    data = response.json()
    print(data)

    ticket_key = data["key"]

    print("Jira ticket created:", ticket_key)

    return ticket_key

# -----------------------------
# SEND EMAIL
# -----------------------------

def send_email(ticket, problem):

    msg = MIMEText(f"New Jira ticket created: {ticket}\n\nIssue: {problem}")

    msg["Subject"] = f"Helpdesk Ticket {ticket}"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print("Email notification sent")

# -----------------------------
# SEND SLACK MESSAGE
# -----------------------------

def send_slack(ticket, problem):

    message = {
        "text": f"🚨 New Helpdesk Ticket Created\nTicket: {ticket}\nIssue: {problem}"
    }

    requests.post(SLACK_WEBHOOK, json=message)

    print("Slack notification sent")

# -----------------------------
# AI AGENT
# -----------------------------

def helpdesk_agent(problem):

    print("\nAnalyzing issue using AI...\n")

    decision = analyze_problem(problem)

    print("AI Decision:", decision)

    priority = decision["priority"]
    issue_type = decision["issue_type"]

    ticket = create_jira_ticket(problem, priority, issue_type)

    if decision["needs_email"]:
        send_email(ticket, problem)

    if decision["needs_slack"]:
        send_slack(ticket, problem)

# -----------------------------
# RUN AGENT
# -----------------------------

problem = input("Describe the problem: ")

helpdesk_agent(problem)
