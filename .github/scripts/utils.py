import os
import logging
import github
import html
import tiktoken
from typing import List, Optional
from config import OPENAI_MODEL, MAX_CHUNK_SIZE, EXCLUDE_FOLDERS, EXCLUDE_FILES

logger = logging.getLogger(__name__)

def get_env_variable(name: str) -> str:
    """Safely retrieve environment variables."""
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} environment variable is not set")
    return value

def init_github_client() -> github.PullRequest.PullRequest:
    """Initialize GitHub client and return the current pull request."""
    github_token = get_env_variable("GITHUB_TOKEN")
    repo_name = get_env_variable("GITHUB_REPOSITORY")
    pr_number = int(get_env_variable("PR_NUMBER"))

    try:
        g = github.Github(github_token)
        repo = g.get_repo(repo_name)
        return repo.get_pull(pr_number)
    except github.GithubException as e:
        logger.error(f"GitHub API error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error when initializing GitHub client: {str(e)}")
        raise

def get_pr_diff(pull_request: github.PullRequest.PullRequest) -> str:
    """Get the diff of the pull request, excluding specified folders and files."""
    try:
        files = pull_request.get_files()
        diff = ""
        for file in files:
            path_parts = file.filename.split('/')

            if (any(folder in EXCLUDE_FOLDERS for folder in path_parts) or
                path_parts[-1] in EXCLUDE_FILES):
                continue

            diff += f"File: {file.filename}\n"
            diff += f"Changes:\n{file.patch}\n\n" if file.patch else "\n"
        return diff
    except github.GithubException as e:
        logger.error(f"GitHub API error when fetching PR diff: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error when fetching PR diff: {str(e)}")
        raise

def sanitize_input(text: Optional[str]) -> str:
    """Sanitize input to prevent potential injection issues."""
    if text is None:
        return ""
    return html.escape(text)

def post_review(pull_request: github.PullRequest.PullRequest, review: str) -> None:
    """Post the review as a comment on the pull request."""
    try:
        pull_request.create_issue_comment(f"AI Code Review:\n\n{review}")
    except github.GithubException as e:
        logger.error(f"GitHub API error when posting review: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error when posting review: {str(e)}")

def count_tokens(text: str) -> int:
    """Count the number of tokens in the given text."""
    encoding = tiktoken.encoding_for_model(OPENAI_MODEL)
    return len(encoding.encode(text))

def split_diff(diff_text: str) -> List[str]:
    """Split the diff into manageable chunks."""
    encoding = tiktoken.encoding_for_model(OPENAI_MODEL)
    tokens = encoding.encode(diff_text)
    total_tokens = len(tokens)

    if total_tokens <= MAX_CHUNK_SIZE:
        return [diff_text]

    chunks = []
    current_chunk = ""
    current_tokens = 0

    lines = diff_text.split('\n')
    for line in lines:
        line_tokens = len(encoding.encode(line + '\n'))
        if current_tokens + line_tokens > MAX_CHUNK_SIZE and current_chunk:
            chunks.append(current_chunk)
            current_chunk = ""
            current_tokens = 0
        current_chunk += line + '\n'
        current_tokens += line_tokens

    if current_chunk:
        chunks.append(current_chunk)

    logger.info(f"Split diff into {len(chunks)} chunks")
    return chunks
