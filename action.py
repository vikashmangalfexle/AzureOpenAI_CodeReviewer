import os
import json
import requests

GITHUB_TOKEN = os.environ["PAT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_API_KEY_HEADER = os.environ["OPENAI_API_KEY_HEADER"]
OPENAI_ENDPOINT = os.environ["OPENAI_ENDPOINT"]

GITHUB_API_URL = "https://api.github.com"

def get_pr_details(event_path):
    with open(event_path, "r") as f:
        event_data = json.load(f)

    repository = event_data["repository"]
    pull_request = event_data["number"]

    repo_full_name = repository["full_name"]
    url = f"{GITHUB_API_URL}/repos/{repo_full_name}/pulls/{pull_request}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}","Accept": "application/vnd.github+json","X-GitHub-Api-Version": "2022-11-28"}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error retrieving pull request: {response.json()}")

    pr = response.json()
    return {
        "owner": repository["owner"]["login"],
        "repo": repository["name"],
        "pull_number": pull_request,
        "title": pr.get("title", ""),
        "description": pr.get("body", "")
    }

def get_diff(owner, repo, pull_number):
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pull_number}/files"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}","X-GitHub-Api-Version": "2022-11-28"}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error retrieving diff: {response.json()}")

    return response.json()

def analyze_code(diff, pr_details):
    comments = []
    for file in diff:
        if file.get("status") == 'removed':
            continue
        # Assume Azure OpenAI API call for code review:
        prompt = create_prompt(file, pr_details)
        ai_response = get_ai_response(prompt)
        if ai_response:
            comments.append(create_comment(file, ai_response))
    return comments

def create_prompt(file, pr_details):
    return f"""Your task is to review pull requests...
    Title: {pr_details['title']}
    Description: {pr_details['description']}
    Diff to review: {file.get("patch", "")}"""

def get_ai_response(prompt):
    headers = {
        OPENAI_API_KEY_HEADER: OPENAI_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
    "messages": [
        {
            "role": "user",
                "content": prompt
        }
    ]
}

    response = requests.post(f"{OPENAI_ENDPOINT}", headers=headers, json=payload)
    result = response.json()
    return result.get("choices", [])[0].get("message").get('content')

def create_comment(file, ai_response):
    # Adjust line number and comment text as needed
    return {
        "path": file["filename"],
        "body": ai_response,
        "line": 1  # Placeholder line number; adjust as needed
    }

def create_review_comment(owner, repo, pull_number, comments):
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    review_body = {
        "event": "COMMENT",
        "body": "Automated code review by OpenAI",
        "comments": comments
    }
    
    response = requests.post(url, headers=headers, json=review_body)
    if response.status_code != 200:
        raise Exception(f"Error creating review: {response.json()}")


if __name__ == "__main__":
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        raise ValueError("GITHUB_EVENT_PATH environment variable is not set")
    
    pr_details = get_pr_details(event_path)
    diff = get_diff(pr_details["owner"], pr_details["repo"], pr_details["pull_number"])

    comments = analyze_code(diff, pr_details)
    if comments:
        create_review_comment(pr_details["owner"], pr_details["repo"], pr_details["pull_number"], comments)
