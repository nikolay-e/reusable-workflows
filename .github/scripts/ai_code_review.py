import os
import logging
import time
from typing import Optional
import github
from openai import OpenAI
from utils import (
    get_env_variable, init_github_client, get_pr_diff,
    sanitize_input, post_review, count_tokens, split_diff
)
from config import OPENAI_MODEL, TOKEN_RESET_PERIOD, MAX_CHUNK_SIZE

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_openai_client() -> OpenAI:
    """Initialize and return the OpenAI client."""
    api_key = get_env_variable("OPENAI_API_KEY")
    return OpenAI(api_key=api_key)

def review_code(client: OpenAI, pr_diff: str, pr_title: str, pr_body: Optional[str]) -> str:
    """Perform AI code review using OpenAI API, and decide on merge readiness."""
    total_tokens = count_tokens(pr_diff)

    if total_tokens <= MAX_CHUNK_SIZE:
        logger.info("PR diff fits within token limit. Proceeding with direct review.")
        content_to_review = f"PR Diff:\n{pr_diff}"
    else:
        logger.info("PR diff exceeds token limit. Splitting into chunks.")
        diff_chunks = split_diff(pr_diff)
        analyses = []
        for i, chunk in enumerate(diff_chunks):
            try:
                response = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "You are an expert code reviewer."},
                        {"role": "user", "content": f"Please review the following code changes:\n\n{chunk}"}
                    ]
                )
                analyses.append(response.choices[0].message.content)
                logger.info(f"Completed review of chunk {i+1}/{len(diff_chunks)}")
                time.sleep(TOKEN_RESET_PERIOD)
            except Exception as e:
                logger.error(f"OpenAI API error during chunk {i+1} review: {str(e)}")
                analyses.append(f"Error occurred during review of chunk {i+1}: {str(e)}")
        content_to_review = "\n\n".join(analyses)

    sanitized_title = sanitize_input(pr_title)
    sanitized_body = sanitize_input(pr_body)

    final_review_prompt = f"""
Based on the following pull request changes:

{content_to_review}

PR Title: {sanitized_title}
PR Body: {sanitized_body}

Please provide a code review that includes:

1. Feedback on:
   - Potential bugs or errors
   - Suggestions for improvement
   - Security concerns
   - Design and architecture considerations

2. A suggested short commit message (max 8 words) that accurately describes the changes.

3. A merge decision (YES/NO) with a brief explanation for your choice.

Structure your response as follows:

Code Review:
[Your detailed review]

Suggested Short Commit Message:
[Your commit message]

Merge Decision: [YES/NO]
[Brief explanation]
"""

    try:
        logger.info("Sending final review request to OpenAI")
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert code reviewer. Provide a comprehensive review based on the provided pull request details."},
                {"role": "user", "content": final_review_prompt}
            ]
        )
        logger.info("Received final review response from OpenAI")
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"OpenAI API error during final review: {str(e)}")
        return f"Error occurred during code review: {str(e)}"

def extract_merge_decision(review: str) -> bool:
    """Extract the merge decision ('YES' or 'NO') from the review."""
    try:
        lines = review.splitlines()
        decision = ""
        found_merge_decision = False

        for line in lines:
            if "Merge Decision:" in line:
                # Check if 'YES' or 'NO' is on the same line after the colon
                parts = line.split(":", 1)
                if len(parts) > 1 and parts[1].strip().upper() in ("YES", "NO"):
                    decision = parts[1].strip().upper()
                    return decision == "YES"
                else:
                    found_merge_decision = True  # Set flag to check the next line
            elif found_merge_decision:
                # Check the next line after 'Merge Decision:'
                stripped_line = line.strip().upper()
                if stripped_line in ("YES", "NO"):
                    decision = stripped_line
                    return decision == "YES"
                else:
                    found_merge_decision = False  # Reset if next line is not 'YES' or 'NO'
        # If 'Merge Decision:' not found or decision not recognized, default to False
        return False
    except Exception as e:
        logger.error(f"Error extracting merge decision: {str(e)}")
        return False

def main():
    try:
        logger.info("Starting code review process")
        openai_client = init_openai_client()
        pull_request = init_github_client()
        logger.info("Fetching pull request diff")
        pr_diff = get_pr_diff(pull_request)
        logger.info("Starting code review")
        review = review_code(openai_client, pr_diff, pull_request.title, pull_request.body)
        logger.info("Posting review")
        post_review(pull_request, review)
        logger.info("Code review process completed successfully")
        merge_decision = extract_merge_decision(review)
        print(f"MERGE_DECISION={'success' if merge_decision else 'failure'}")
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
    except github.GithubException as e:
        logger.error(f"GitHub API error: {str(e)}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main()
