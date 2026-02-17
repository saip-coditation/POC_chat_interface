import os
import threading
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


def _preload_local_embeddings():
    """Preload sentence-transformers on Render so first request doesn't wait 60s."""
    try:
        from rag.embeddings import LocalEmbeddings
        e = LocalEmbeddings()
        e.embed("warmup")  # Load model
        logger.info("Preloaded local embeddings (Render)")
    except Exception as exc:
        logger.warning("Preload local embeddings skipped: %s", exc)


class OrchestratorConfig(AppConfig):
    name = 'orchestrator'

    def ready(self):
        if os.getenv("RENDER"):
            threading.Thread(target=_preload_local_embeddings, daemon=True).start()
