# Webhook Receiver

Servidor de recebimento de webhooks com autenticação via **Token Dinâmico (OAuth 2.0)**,
compatível com o Pandapé ATS e qualquer plataforma que implemente o fluxo
`client_credentials` da RFC 6749.

Hospedado no [Render](https://render.com) (plano gratuito), mantido acordado pelo
[UptimeRobot](https://uptimerobot.com).

**URL em produção:** `https://webhook-receiver-v18x.onrender.com`

---

## Como funciona

```
Pandapé                          Webhook Receiver (este projeto)
   │                                        │
   │  POST /oauth/token                     │
   │  Content-Type: application/x-www-form-urlencoded
   │  grant_type=client_credentials         │
   │  client_id=...  client_secret=...      │
   │ ─────────────────────────────────────► │
   │                                        │
   │  200 OK                                │
   │  { "access_token": "eyJ...",           │
   │    "token_type": "Bearer",             │
   │    "expires_in": 3600 }                │
   │ ◄───────────────────────────────────── │
   │                                        │
   │  POST /webhook/pandape                 │
   │  Authorization: Bearer eyJ...          │
   │  { ...payload do evento... }           │
   │ ─────────────────────────────────────► │
   │                                        │
   │  200 OK { "status": "received" }       │
   │ ◄───────────────────────────────────── │
```

---

## Endpoints

| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/oauth/token` | `client_id` + `client_secret` | Emite um Bearer token |
| `POST` | `/webhook/pandape` | Bearer token | Recebe eventos do Pandapé |
| `GET` | `/health` | Nenhuma | Health check (UptimeRobot) |

---

## Requisitos técnicos

- Python 3.10+
- Dependências: `flask`, `gunicorn`, `PyJWT`, `python-dotenv`

### Variáveis de ambiente

| Variável | Obrigatória | Padrão (dev local) | Descrição |
|---|---|---|---|
| `CLIENT_ID` | Sim | `pandape-client-id` | Identificador enviado pelo Pandapé |
| `CLIENT_SECRET` | Sim | gerado em `.client_secret` | Segredo enviado pelo Pandapé |
| `JWT_SECRET_KEY` | Sim | gerado em `.jwt_secret_key` | Chave de assinatura dos tokens — nunca compartilhe |
| `TOKEN_EXPIRES_IN` | Não | `3600` | Validade do Bearer token em segundos |
| `PORT` | Não | `5000` | Porta do servidor (Render define automaticamente) |

---

## Rodar localmente

```bash
# 1. Clonar e entrar na pasta
git clone https://github.com/gabrxgomes/webhook-receiver.git
cd webhook-receiver

# 2. Criar virtualenv e instalar dependências
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configurar variáveis (opcional — sem .env o app gera segredos automaticamente)
cp .env.example .env
# edite .env com seus valores

# 4. Iniciar o servidor
./start.sh
```

Servidor disponível em `http://localhost:5000`.

---

## Testar

### Via curl

```bash
# 1. Gerar Bearer token (form-encoded — mesmo formato que o Pandapé usa)
curl -X POST http://localhost:5000/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=pandape-client-id&client_secret=pandape-client-secret"

# Resposta:
# { "access_token": "eyJ...", "token_type": "Bearer", "expires_in": 3600 }

# 2. Enviar webhook com o token recebido
TOKEN="cole_o_access_token_aqui"

curl -X POST http://localhost:5000/webhook/pandape \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event": "candidato.inscrito", "candidato": {"id": 1, "nome": "João Silva"}}'

# Resposta:
# { "status": "received", "message": "Webhook do Pandape recebido com sucesso", ... }

# 3. Health check
curl http://localhost:5000/health
# { "status": "ok" }

# 4. Testar rejeição (credenciais erradas → 401)
curl -i -X POST http://localhost:5000/oauth/token \
  -d "grant_type=client_credentials&client_id=errado&client_secret=errado"
```

### Via Postman

Importe o arquivo `postman/Pandape_Webhook.postman_collection.json`, ajuste as
variáveis `base_url`, `client_id` e `client_secret`, e execute as requisições
na ordem:

1. **Get Bearer Token** — obtém o token e salva automaticamente na coleção
2. **Send Webhook (Pandape)** — envia payload usando o token do passo 1
3. **Health Check** — confirma que o serviço está no ar

---

## Deploy no Render

Consulte o [DEPLOY_RENDER.md](DEPLOY_RENDER.md) para o guia completo, incluindo
configuração das variáveis de ambiente, UptimeRobot e integração com o Pandapé.

Resumo dos campos no Render:

| Campo | Valor |
|---|---|
| Runtime | `Python 3` |
| Instance Type | `Free` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app --bind 0.0.0.0:$PORT` |

---

## Configurar no Pandapé

**Configurações → Webhooks → Novo Webhook**

| Campo | Valor |
|---|---|
| Tipo de autorização | Token dinâmico |
| URL do token | `https://webhook-receiver-v18x.onrender.com/oauth/token` |
| Client ID | valor de `CLIENT_ID` (Render → Environment) |
| Client Secret | valor de `CLIENT_SECRET` (Render → Environment) |
| URL de destino | `https://webhook-receiver-v18x.onrender.com/webhook/pandape` |

Use o botão **Testar Webhook** antes de salvar para confirmar a conectividade.

---

## Ver webhooks recebidos

Render → serviço `webhook-receiver` → aba **Logs**.

```
============================================================
[2026-07-03 10:15:00] WEBHOOK RECEIVED [PANDAPE]
  Method      : POST
  Content-Type: application/json

  --- Body (JSON) ---
  {
    "event": "candidato.inscrito",
    "candidato": { "id": 1, "nome": "João Silva" }
  }
============================================================
```

Tentativas rejeitadas também são registradas:
```
[2026-07-03 10:15:00] UNAUTHORIZED - Bearer token invalido, expirado ou ausente
[2026-07-03 10:15:00] TOKEN REQUEST REJECTED - client_id/secret invalidos
```
