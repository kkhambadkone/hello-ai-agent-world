import requests
import json
import re
import smtplib
from email.mime.text import MIMEText

# -----------------------------
# CONFIGURATION
# -----------------------------

# Ollama LLM
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"

# Jira
JIRA_URL = "<JIRA_URL>"
JIRA_EMAIL = "<EMAIL>"
JIRA_API_TOKEN = "<JIRA_API_TOKEN>"
JIRA_PROJECT_KEY = "<JIRA_PROJECT_KEY>"

# Email
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "<FROM_EMAIL>"
EMAIL_PASS = "<PASSWO>RD>"  # For Gmail, use App Password
EMAIL_TO = "<TO_EMAIL>"

# Slack
SLACK_WEBHOOK = "<SLACK_WEBHOOK>"

# -----------------------------
# LLM ANALYSIS
# -----------------------------

# Describe the problem: 
# the problem: The payment API is failing and customers cannot checkout.

# Analyzing issue using AI...

# AI Decision: {'priority': 'High', 'issue_type': 'Bug', 'needs_slack': True, 'needs_email': True, 'summary': 'Payment API Failing', 'description': 'The payment API is failing, preventing customers from checking out.'}
# {'id': '10176', 'key': 'SCRUM-39', 'self': 'https://krish-ai-test.atlassian.net/rest/api/3/issue/10176'}
# Jira ticket created: SCRUM-39
# EEmail notification sent
# Slack notification sent

# Describe the problem: 
# Create a product selection page where users can choose:
# - Product category from a dropdown
# - Product brand from a dropdown
# - Delivery speed using radio buttons
# - Warranty option using radio buttons
# The page should also include a submit button and validation if nothing is selected.

# Analyzing issue using AI...

# AI Decision: {'priority': 'Medium', 'issue_type': 'Story', 'needs_slack': False, 'needs_email': False, 'summary': 'Add product selection page features', 'description': 'Create a product selection page where users can choose:\n- Product category from a dropdown\n- Product brand from a dropdown\n- Delivery speed using radio buttons\n- Warranty option using radio buttons\nThe page should also include a submit button and validation if nothing is selected.'}
# {'id': '10177', 'key': 'SCRUM-40', 'self': 'https://krish-ai-test.atlassian.net/rest/api/3/issue/10177'}
# Jira ticket created: SCRUM-40

def analyze_problem(problem):

    # FIX 1: The description field in the 2nd few-shot example previously used a
    # raw multi-line string, which is invalid JSON. JSON strings must be on a single
    # line with \n for newlines. The model was learning this broken pattern and
    # replicating it, causing json.decoder.JSONDecodeError.
    prompt = f"""

You are an AI Helpdesk Agent for an engineering team that converts user problems into structured JIRA ticket metadata.

Follow these steps:

Step 1: Understand the problem.
Step 2: Determine if it is a Bug, Task, or Story.
Step 3: Determine priority based on impact.
Step 4: Decide if Slack notification is needed (urgent issues).
Step 5: Decide if Email notification is needed (stakeholder visibility).

Definitions:

Bug: 
Something that is broken or not working.

Task:
Operational request or configuration change.

Story:
New feature request or enhancement.
Priority Rules:

High:
System outages, production failures, or security problems.

Medium:
Feature work or partial functionality issues.

Low:
Minor requests or documentation updates.

Classify the issue and return JSON with the following fields:

priority: Low | Medium | High
issue_type: Bug | Task | Story
needs_slack: true | false
needs_email: true | false
summary: short one-line title for the ticket
description: full description of the issue (use \\n for newlines, keep on a single line)


Example 1:
Here are an example of a Bug. 

Problem:
"The company website shows a 500 error when users try to login."

Output:
{{
  "priority": "High",
  "issue_type": "Bug",
  "needs_slack": true,
  "needs_email": true
  "summary": "User Login Issue",
  "description": "The company website shows a 500 error when users try to login."
}}


Example 2:
Here are an example of a Task.

Problem:
"The product page should allow users to select a product category and a brand from dropdowns, choose delivery speed using radio buttons, and select warranty options."

Output:
{{
  "priority": "Medium",
  "issue_type": "Story",
  "needs_slack": false,
  "needs_email": false,
  "summary": "Add selection features to product page",
  "description": "Include the following features:\\n1. Allow users to select a product category and a brand from dropdowns.\\n2. Choose delivery speed using radio buttons.\\n3. Select warranty options."
}}

Now analyze the following problem.

Problem:
{problem}

RULES:
1. Return ONLY valid JSON.
2. JSON must start with {{ and end with }}.
3. Include all fields: 
   - priority (Low, Medium, High)
   - issue_type (Bug, Feature, Task)
   - needs_slack (true/false)
   - needs_email (true/false)
   - summary (short summary)
   - description (detailed description)
4. Escape all line breaks inside strings using \\n.
5. Do NOT include any extra text, explanations, or notes.

"""

#Return ONLY valid JSON. Make sure it starts with {{ and ends with }}. No explanations. No markdown fences.

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        }
    )

    result = response.json()["response"]

    # FIX 2: Strip markdown fences if the model wraps output in ```json ... ```
    # despite being told not to — LLMs sometimes do this anyway.
    result = result.strip()
    result = re.sub(r"^```(?:json)?\s*", "", result)
    result = re.sub(r"\s*```$", "", result)

    # FIX 3: Extract the first JSON object found, in case the model adds
    # any trailing commentary after the closing brace.
    match = re.search(r"\{.*\}", result, re.DOTALL)
    if not match:
        raise ValueError(f"No valid JSON object found in LLM response:\n{result}")

    return json.loads(match.group())

# -----------------------------
# CREATE JIRA TICKET
# -----------------------------

def create_jira_ticket(summary, description, priority, issue_type):

    url = f"{JIRA_URL}/rest/api/3/issue"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    summary = summary[:255]

    # Build description content: split on \n to create separate paragraphs
    description_paragraphs = []
    for line in description.split("\n"):
        line = line.strip()
        if line:
            description_paragraphs.append({
                "type": "paragraph",
                "content": [{"text": line, "type": "text"}]
            })

    if not description_paragraphs:
        description_paragraphs = [{
            "type": "paragraph",
            "content": [{"text": summary, "type": "text"}]
        }]

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
                "content": description_paragraphs
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

    priority   = decision.get("priority", "Medium")
    issue_type = decision.get("issue_type", "Task")
    summary    = decision.get("summary", problem[:80])
    description = decision.get("description", problem)

    ticket = create_jira_ticket(summary, description, priority, issue_type)

    if decision.get("needs_email"):
        send_email(ticket, problem)

    if decision.get("needs_slack"):
        send_slack(ticket, problem)

# -----------------------------
# RUN AGENT
# -----------------------------

print("Describe the problem: ")

lines = []
while True:
    line = input()
    if line == "":
        break
    lines.append(line)

problem = "\n".join(lines)

helpdesk_agent(problem)
