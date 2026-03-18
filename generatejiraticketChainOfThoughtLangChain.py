"""
Helpdesk Agent — Jira ticket generator
Refactored to use LangChain (OllamaLLM + PromptTemplate + JsonOutputParser).

Install:
    pip install langchain langchain-ollama pydantic requests

Run:
    python generatejiraticketChainOfThought.py
"""

import smtplib
from email.mime.text import MIMEText

import requests
from pydantic import BaseModel, Field

# ── LangChain ─────────────────────────────────────────────────────────────────
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Ollama LLM
MODEL = "llama3"

# Jira
JIRA_URL         = "<JIRA_URL>"
JIRA_EMAIL       = "<JIRA_EMAIL>"
JIRA_API_TOKEN   = "<JIRA_API_TOKEN>"
JIRA_PROJECT_KEY = "<JIRA_PROJECT_KEY>"

# Email
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT   = 587
EMAIL_USER  = "<EMAIL_USER>"
EMAIL_PASS  = "<EMAIL_PASS>"   # Gmail App Password
EMAIL_TO    = "<EMAIL_TO>"

# Slack
SLACK_WEBHOOK = "<SLACK_WEBHOOK>"

# ==============================================================================
# LANGCHAIN — structured output schema
# ==============================================================================

class TicketDecision(BaseModel):
    priority:    str  = Field(description="Low | Medium | High")
    issue_type:  str  = Field(description="Bug | Task | Story")
    needs_slack: bool = Field(description="True if Slack notification required")
    needs_email: bool = Field(description="True if email notification required")
    summary:     str  = Field(description="Short one-line title for the Jira ticket")
    description: str  = Field(description="Full description (use \\n for newlines)")


# Build the chain once — reused for every call
_llm    = OllamaLLM(model=MODEL)
_parser = JsonOutputParser(pydantic_object=TicketDecision)

# Prompt Example  1 (Bug):
# the problem: The payment API is failing and customers cannot checkout.

# Prompt Example 2 (Story):
# Create a product selection page where users can choose:
#  - Product category from a dropdown
#  - Product brand from a dropdown
#  - Delivery speed using radio buttons
#  - Warranty option using radio buttons


_prompt = PromptTemplate(
    input_variables=["problem", "format_instructions"],
    template="""

You are an AI Helpdesk Agent for an engineering team that converts user problems into structured JIRA ticket metadata.

Follow these steps:

Step 1: Understand the problem.
Step 2: Determine if it is a Bug, Task, or Story.
Step 3: Determine priority based on impact.
Step 4: Decide if Slack notification is needed (urgent issues).
Step 5: Decide if Email notification is needed (stakeholder visibility).

Definitions:

Bug:
Something broken or not working.

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
  "needs_email": true,
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


Now analyze the following problem:

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

IMPORTANT: Output ONLY the raw JSON object. No preamble. No explanation. No markdown. Start with {{ and end with }}.
""",
)

# LangChain LCEL chain:  prompt | llm | json_parser
_chain = _prompt | _llm | _parser

# ==============================================================================
# LLM ANALYSIS
# ==============================================================================

def analyze_problem(problem: str) -> dict:
    """Use LangChain + Ollama to classify a problem into Jira ticket metadata."""
    decision = _chain.invoke({
        "problem": problem,
        "format_instructions": _parser.get_format_instructions(),
    })
    print("-----------AI DECISION---------")
    print(decision)
    # JsonOutputParser may return a TicketDecision instance or a plain dict
    if isinstance(decision, TicketDecision):
        decision = decision.model_dump()
    return decision

# ==============================================================================
# CREATE JIRA TICKET
# ==============================================================================

def create_jira_ticket(summary: str, description: str, priority: str, issue_type: str) -> str:
    """Create a Jira issue and return its ticket key (e.g. SCRUM-42)."""
    url     = f"{JIRA_URL}/rest/api/3/issue"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    summary = summary[:255]

    paragraphs = [
        {
            "type": "paragraph",
            "content": [{"text": line.strip(), "type": "text"}],
        }
        for line in description.split("\n")
        if line.strip()
    ] or [{"type": "paragraph", "content": [{"text": summary, "type": "text"}]}]

    payload = {
        "fields": {
            "project":     {"key": JIRA_PROJECT_KEY},
            "summary":     summary,
            "issuetype":   {"name": issue_type},
            "priority":    {"name": priority},
            "description": {"type": "doc", "version": 1, "content": paragraphs},
        }
    }

    response = requests.post(
        url, json=payload, headers=headers, auth=(JIRA_EMAIL, JIRA_API_TOKEN)
    )
    data = response.json()
    print(data)

    ticket_key = data["key"]
    print("Jira ticket created:", ticket_key)
    return ticket_key

# ==============================================================================
# SEND EMAIL
# ==============================================================================

def send_email(ticket: str, problem: str) -> None:
    """Send an email notification for a newly created Jira ticket."""
    msg            = MIMEText(f"New Jira ticket created: {ticket}\n\nIssue: {problem}")
    msg["Subject"] = f"Helpdesk Ticket {ticket}"
    msg["From"]    = EMAIL_USER
    msg["To"]      = EMAIL_TO

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print("Email notification sent")

# ==============================================================================
# SEND SLACK MESSAGE
# ==============================================================================

def send_slack(ticket: str, problem: str) -> None:
    """Post a Slack notification for a newly created Jira ticket."""
    message = {"text": f"🚨 New Helpdesk Ticket Created\nTicket: {ticket}\nIssue: {problem}"}
    requests.post(SLACK_WEBHOOK, json=message)
    print("Slack notification sent")

# ==============================================================================
# AI AGENT
# ==============================================================================

def helpdesk_agent(problem: str) -> None:
    print("\nAnalyzing issue using AI...\n")

    decision = analyze_problem(problem)
    print("AI Decision:", decision)

    priority    = decision.get("priority",    "Medium")
    issue_type  = decision.get("issue_type",  "Task")
    summary     = decision.get("summary",     problem[:80])
    description = decision.get("description", problem)

    ticket = create_jira_ticket(summary, description, priority, issue_type)

    if decision.get("needs_email"):
        send_email(ticket, problem)

    if decision.get("needs_slack"):
        send_slack(ticket, problem)

# ==============================================================================
# RUN AGENT
# ==============================================================================

print("Describe the problem: ")

lines = []
while True:
    line = input()
    if line == "":
        break
    lines.append(line)

problem = "\n".join(lines)

helpdesk_agent(problem)
