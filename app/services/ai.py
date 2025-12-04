import logging
from functools import lru_cache
from typing import Sequence

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _build_pipeline(model_name: str):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    return pipeline("text2text-generation", model=model, tokenizer=tokenizer)


class AIInsightsService:
    def __init__(self):
        self.model_name = settings.ai_model

    def summarize_validations(self, *, validations: Sequence[dict], sample_rows: Sequence[dict]) -> str:
        prompt = (
            "Eres un analista de calidad de datos. Resume el estado del archivo y sugiere una "
            "acción concreta en un máximo de 80 palabras.\n\n"
            f"Validaciones: {validations}\nMuestra: {sample_rows[:3]}"
        )
        try:
            gen = _build_pipeline(self.model_name)(
                prompt,
                max_length=120,
                num_return_sequences=1,
                clean_up_tokenization_spaces=True,
            )
            return gen[0]["generated_text"].strip()
        except Exception as exc:  # pragma: no cover - dependencias externas
            logger.exception("Fallo al generar resumen con el modelo local: %s", exc)
            return "IA local no disponible en este momento; verifica los paquetes transformers/torch."


