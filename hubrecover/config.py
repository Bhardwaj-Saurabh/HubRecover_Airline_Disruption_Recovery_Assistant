"""Load only HubRecover's model settings from the repository-local ignored .env."""
import os
from pathlib import Path
from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parent.parent / '.env'
MODEL_SETTINGS = ('GOOGLE_API_KEY', 'HUBRECOVER_GEMINI_MODEL')


def load_local_environment(path=None):
    # No shell evaluation, variable expansion or searching parent directories.
    # Explicit process settings take precedence over the local development file.
    values=dotenv_values(Path(path) if path is not None else ENV_FILE,interpolate=False)
    for name in MODEL_SETTINGS:
        value=values.get(name)
        if value:
            os.environ.setdefault(name,value)
