"""Carregamento fail-closed de credenciais BYOK no Cloud Run Job."""
import re


def personal_agent_environment(current: dict, db, project: str, owner_uid: str, *,
                               manager=None) -> dict:
    """Retorna env isolado para o processo filho; nunca usa ADC/Vertex por engano."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", owner_uid):
        raise RuntimeError("Identidade inválida")
    snap = db.collection("research_credentials").document(owner_uid).get()
    if not snap.exists or snap.to_dict().get("status") != "active":
        raise RuntimeError("Credencial pessoal indisponível")
    path = f"projects/{project}/secrets/scriptorium-byok-{owner_uid}"
    if snap.to_dict().get("secret_resource") != path:
        raise RuntimeError("Caminho da credencial inválido")
    if manager is None:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
    else:
        client = manager
    response = client.access_secret_version(request={"name": path + "/versions/latest"})
    key = response.payload.data.decode("utf-8")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,512}", key):
        raise RuntimeError("Chave pessoal inválida")
    # Limpa TODAS as fontes herdadas que poderiam direcionar ao projeto do mantenedor.
    env = dict(current)
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "VERTEX_AI_PROJECT",
                 "VERTEX_AI_LOCATION", "GOOGLE_CLOUD_LOCATION", "GOOGLE_CLOUD_PROJECT",
                 "GOOGLE_GENAI_USE_VERTEXAI"):
        env.pop(name, None)
    env["GEMINI_API_KEY"] = key
    env["GOOGLE_API_KEY"] = key
    env["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
    return env
