import os
import json
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv()

app = Flask(__name__)

BASE_DIR = os.path.dirname(__file__)
PORT = int(os.environ.get("PORT", 5000))


def load_or_create_secret(env_var, file_name, length=32):
    env_val = os.environ.get(env_var)
    if env_val:
        return env_val

    path = os.path.join(BASE_DIR, file_name)
    if os.path.exists(path):
        with open(path, "r") as f:
            val = f.read().strip()
            if val:
                return val

    val = secrets.token_urlsafe(length)
    with open(path, "w") as f:
        f.write(val)
    return val


CLIENT_ID = os.environ.get("CLIENT_ID", "pandape-client-id")
CLIENT_SECRET = load_or_create_secret("CLIENT_SECRET", ".client_secret")
JWT_SECRET_KEY = load_or_create_secret("JWT_SECRET_KEY", ".jwt_secret_key")
TOKEN_EXPIRES_IN = int(os.environ.get("TOKEN_EXPIRES_IN", "3600"))


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def extract_client_credentials(req):
    """
    Pandape envia credenciais como form-encoded (application/x-www-form-urlencoded)
    com grant_type, client_id, client_secret.
    Tambem aceita Basic Auth e JSON para testes locais.
    """
    auth = req.authorization
    if auth is not None and auth.type == "basic":
        return auth.username, auth.password

    body = req.get_json(silent=True) or {}
    client_id = body.get("client_id") or req.form.get("client_id")
    client_secret = body.get("client_secret") or req.form.get("client_secret")
    return client_id, client_secret


def credentials_valid(client_id, client_secret):
    if not client_id or not client_secret:
        return False
    return (
        hmac.compare_digest(client_id, CLIENT_ID)
        and hmac.compare_digest(client_secret, CLIENT_SECRET)
    )


def generate_bearer_token(client_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": client_id,
        "iat": now,
        "exp": now + timedelta(seconds=TOKEN_EXPIRES_IN),
        "scope": "webhook:receive",
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")


def verify_bearer_token(req):
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):]
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def mask_secret(value, keep=4):
    if not value:
        return value
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}...{value[-keep:]}"


def log_token_request(req):
    content_type = req.content_type or ""
    auth_header = req.headers.get("Authorization", "")

    print(flush=True)
    print("=" * 60, flush=True)
    log("TOKEN REQUEST RECEBIDO [OAUTH]")
    print(f"  Method      : {req.method}", flush=True)
    print(f"  Content-Type: {content_type}", flush=True)
    if auth_header:
        scheme, _, value = auth_header.partition(" ")
        print(f"  Authorization: {scheme} {mask_secret(value)}", flush=True)
    print(flush=True)

    if req.form:
        print("  --- Form data (x-www-form-urlencoded) ---", flush=True)
        for key, value in req.form.items():
            shown = mask_secret(value) if key == "client_secret" else value
            print(f"    {key} = {shown}", flush=True)

    json_body = req.get_json(silent=True)
    if json_body:
        masked = dict(json_body)
        if "client_secret" in masked:
            masked["client_secret"] = mask_secret(masked["client_secret"])
        print("  --- Body (JSON) ---", flush=True)
        print(json.dumps(masked, indent=2, ensure_ascii=False), flush=True)

    if not req.form and not json_body:
        raw = req.get_data(as_text=True)
        print("  --- Raw body ---", flush=True)
        print(f"  {raw[:2000]}", flush=True)

    print("=" * 60, flush=True)
    print(flush=True)


def log_webhook(req, label):
    content_type = req.content_type or ""
    try:
        payload = req.get_json(force=True, silent=True)
    except Exception:
        payload = None

    print(flush=True)
    print("=" * 60, flush=True)
    log(f"WEBHOOK RECEIVED [{label}]")
    print(f"  Method      : {req.method}", flush=True)
    print(f"  Content-Type: {content_type}", flush=True)
    print(flush=True)
    print("  --- Body (JSON) ---", flush=True)
    if payload is not None:
        print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
    else:
        raw = req.get_data(as_text=True)
        print(f"  (raw) {raw[:2000]}", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)
    return payload


@app.route("/oauth/token", methods=["POST"])
def issue_token():
    """
    Endpoint OAuth 2.0 client_credentials.
    O Pandape chama este endpoint antes de cada envio de webhook para obter um Bearer token.

    Formatos aceitos:
      - form-encoded (padrao do Pandape):
          grant_type=client_credentials&client_id=...&client_secret=...
      - HTTP Basic Auth header
      - JSON body: {"client_id": "...", "client_secret": "..."}
    """
    log_token_request(request)
    client_id, client_secret = extract_client_credentials(request)

    if not credentials_valid(client_id, client_secret):
        log("TOKEN REQUEST REJECTED - client_id/secret invalidos")
        resp = jsonify({
            "error": "invalid_client",
            "error_description": "client_id ou client_secret invalidos",
        })
        resp.status_code = 401
        resp.headers["WWW-Authenticate"] = 'Basic realm="oauth/token"'
        return resp

    token = generate_bearer_token(CLIENT_ID)
    log(f"TOKEN EMITIDO para client_id={CLIENT_ID}")
    return jsonify({
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": TOKEN_EXPIRES_IN,
    }), 200


@app.route("/webhook/pandape", methods=["POST"])
def webhook_pandape():
    """
    Recebe webhooks do Pandape autenticados com Bearer token.
    O Pandape primeiro chama /oauth/token, depois envia o webhook aqui
    com o access_token no header Authorization: Bearer.
    """
    token_payload = verify_bearer_token(request)
    if token_payload is None:
        log("UNAUTHORIZED - Bearer token invalido, expirado ou ausente")
        resp = jsonify({"error": "Unauthorized"})
        resp.status_code = 401
        resp.headers["WWW-Authenticate"] = 'Bearer realm="webhook"'
        return resp

    log_webhook(request, "PANDAPE")
    return jsonify({
        "status": "received",
        "message": "Webhook do Pandape recebido com sucesso",
        "token_subject": token_payload.get("sub"),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    public_url = os.environ.get("RENDER_EXTERNAL_URL", f"http://localhost:{PORT}")

    print(flush=True)
    print("=" * 60, flush=True)
    print("  Pandape Webhook Receiver", flush=True)
    print(f"  Port           : {PORT}", flush=True)
    print(f"  Token endpoint : {public_url}/oauth/token", flush=True)
    print(f"  Webhook URL    : {public_url}/webhook/pandape", flush=True)
    print(f"  Health check   : {public_url}/health", flush=True)
    print(f"  Client ID      : {CLIENT_ID}", flush=True)
    print(f"  Client secret  : {CLIENT_SECRET}", flush=True)
    print(f"  Token TTL      : {TOKEN_EXPIRES_IN}s", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)

    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
