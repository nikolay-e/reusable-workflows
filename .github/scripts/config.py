# config.py

# Configuration
SUPPORTED_FILE_TYPES = ('.py', '.js', '.ts', '.html', '.css', '.yml', '.yaml', '.json', '.md', '.txt')
EXCLUDE_FOLDERS = {'.git', 'node_modules', 'venv', '__pycache__'}
EXCLUDE_FILES = {'package-lock.json', 'yarn.lock'}

OPENAI_MODEL = "gpt-4o"
TOKEN_RESET_PERIOD = 60  # seconds
MAX_CHUNK_SIZE = 30000  # Max tokens per request
