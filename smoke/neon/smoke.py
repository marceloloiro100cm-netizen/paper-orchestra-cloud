"""Teste real e econômico do Neon usando identidade ADC do Cloud Run Job.

Documentação oficial:
https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-4-neon
"""
import os
from google import genai
from google.genai import types

project = os.getenv("GOOGLE_CLOUD_PROJECT")
assert project == "paperorchestra-mestrado", "Projeto inesperado"
client = genai.Client(enterprise=True, project=project, location="global")
try:
    response = client.models.generate_content(
        model="gemini-4-neon",
        contents="Responda apenas com a palavra NEON_OK.",
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="LOW"),
            max_output_tokens=2048,
        ),
    )
    answer = (response.text or "").strip()
    if "NEON_OK" not in answer:
        raise RuntimeError("Neon não devolveu a confirmação esperada.")
    usage = response.usage_metadata
    print("NEON_SMOKE_OK model=gemini-4-neon project=paperorchestra-mestrado "
          "principal=worker-service-account")
    if usage:
        print("USAGE input_tokens=", getattr(usage, "prompt_token_count", None),
              "output_tokens=", getattr(usage, "candidates_token_count", None),
              "thinking_tokens=", getattr(usage, "thoughts_token_count", None))
finally:
    client.close()
