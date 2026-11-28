"""Settings, read from the environment or from butler.env in the repo root."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load KEY=VALUE lines from butler.env; real environment variables win.
_env_file = os.path.join(ROOT, "butler.env")
if os.path.exists(_env_file):
    for _line in open(_env_file):
        if "=" in _line and not _line.lstrip().startswith("#"):
            _key, _value = _line.strip().split("=", 1)
            os.environ.setdefault(_key, _value)


def _get(name, default=""):
    return os.environ.get(name, default)


PORT = int(_get("PORT", "8080"))
DB_PATH = _get("DB", os.path.join(ROOT, "graveyard.db"))

# Only the holder of this key may feed the Taster.
OWNER_KEY = _get("TASTER_KEY")

# The Sprite that eats, and the checkpoint it is restored from.
SPRITES_API = _get("SPRITES_API", "https://api.sprites.dev").rstrip("/")
SPRITES_TOKEN = _get("SPRITES_TOKEN")
TASTER = _get("TASTER", "taster")
CLEAN_CHECKPOINT = _get("CLEAN")
MEAL_TIMEOUT = int(_get("MEAL_TIMEOUT", "45"))

# Pinecone connector gateway: memory of past deaths.
PINECONE_URL = _get("PINECONE_BASE").rstrip("/")
PINECONE_INDEX = _get("PINECONE_INDEX", "taster-past-lives")
SAME_DEATH_SCORE = float(_get("DEJA_VU", "0.90"))

# Gemini connector gateway: writes the autopsy. Models are tried in order.
GEMINI_URL = _get("LLM_BASE").rstrip("/")
GEMINI_MODELS = [m for m in _get("LLM_MODEL").split(",") if m]
