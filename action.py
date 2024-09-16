import os
import json
import requests

GITHUB_TOKEN = os.environ["PAT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.environ["OPENAI_MODEL"]
OPENAI_ENDPOINT = os.environ["OPENAI_ENDPOINT"]

GITHUB_API_URL = "https://api.github.com"
print(f"GITHUB_TOKEN: {GITHUB_TOKEN}")
print(f"OPENAI_API_KEY: {OPENAI_API_KEY}")
print(f"OPENAI_MODEL: {OPENAI_MODEL}")
print(f"OPENAI_ENDPOINT: {OPENAI_ENDPOINT}")

def get_pr_details(event_path):
    with open(event_path, "r") as f:
        event_data = json.load(f)

    repository = event_data["repository"]
    pull_request = event_data["number"]
    print(GITHUB_TOKEN)
    print(f"Repository: {repository['full_name']}")
    print(f"Pull Request Number: {pull_request}")

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
        "api-key": OPENAI_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": prompt,
        "model": OPENAI_MODEL,
        "max_tokens": 700,
        "temperature": 0.2
    }

    response = requests.post(f"{OPENAI_ENDPOINT}/openai/deployments/{OPENAI_MODEL}/completions", headers=headers, json=payload)
    result = response.json()
    return result.get("choices", [])[0].get("text")

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
    
    """review_id = response.json().get("id")

    for comment in comments:
        comment_url = f"{url}/{review_id}/comments"
        comment_body = {
            "body": comment["body"],
            "path": comment["path"],
            "line": comment["line"]
        }
        response = requests.post(comment_url, headers=headers, json=comment_body)
        if response.status_code != 201:
            print(f"Error adding comment: {response.json()}")"""

if __name__ == "__main__":
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        raise ValueError("GITHUB_EVENT_PATH environment variable is not set")
    
    pr_details = get_pr_details(event_path)
    diff = get_diff(pr_details["owner"], pr_details["repo"], pr_details["pull_number"])
    test_comments = [{
            "body": "Test Ai code Review",
            "path": "Test.txt",
            "line": 2
        }]
    create_review_comment(pr_details["owner"], pr_details["repo"], pr_details["pull_number"],test_comments)

    # comments = analyze_code(diff, pr_details)
    # if comments:
    #     create_review_comment(pr_details["owner"], pr_details["repo"], pr_details["pull_number"], comments)
