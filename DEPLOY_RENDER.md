# Deploy no Render — Pandape Webhook Receiver

Guia completo para colocar o serviço no ar no Render (plano gratuito) e mantê-lo
acordado com o UptimeRobot.

---

## 1. Suba o código para o GitHub

Se ainda não tem o repositório no GitHub:

```bash
# Dentro da pasta pandape_webhook
git init
git add .
git commit -m "Initial commit"
gh repo create pandape-webhook --public --source=. --remote=origin --push
```

> Se não usar a CLI `gh`, crie o repositório em github.com e faça o push manualmente:
> ```bash
> git remote add origin https://github.com/SEU_USUARIO/pandape-webhook.git
> git push -u origin main
> ```

---

## 2. Crie o Web Service no Render

1. Acesse [dashboard.render.com](https://dashboard.render.com) e faça login.
2. Clique em **New** → **Web Service**.
3. Conecte sua conta GitHub se solicitado, depois selecione o repositório `pandape-webhook`.
4. Preencha as configurações:

   | Campo           | Valor                                      |
   |-----------------|--------------------------------------------|
   | Name            | `pandape-webhook` (ou o nome que quiser)   |
   | Runtime         | `Python 3`                                 |
   | Instance Type   | **Free**                                   |
   | Build Command   | `pip install -r requirements.txt`          |
   | Start Command   | `gunicorn app:app --bind 0.0.0.0:$PORT`    |

5. Na seção **Environment Variables**, adicione:

   | Variável         | Valor / Ação                                         |
   |------------------|-------------------------------------------------------|
   | `CLIENT_ID`      | Escolha um nome, ex.: `pandape_webhook_prod`         |
   | `CLIENT_SECRET`  | Clique em **Generate** (o Render cria um valor forte) |
   | `JWT_SECRET_KEY` | Clique em **Generate**                               |
   | `TOKEN_EXPIRES_IN` | `3600`                                             |

6. Clique em **Create Web Service**.
7. Aguarde o build terminar (cerca de 1-2 min). Ao final, sua URL será:
   ```
   https://webhook-receiver-v18x.onrender.com
   ```

---

## 3. Verifique o deploy

```bash
curl https://webhook-receiver-v18x.onrender.com/health
```

Resposta esperada:
```json
{"status": "ok"}
```

Se a primeira chamada demorar ~30s, é normal — o plano gratuito "dorme" após
15 min de inatividade. O UptimeRobot (passo 5) resolve isso.

---

## 4. Configure o Webhook no Pandapé

No painel do Pandapé, vá em **Configurações → Webhooks → Novo Webhook** e
preencha:

| Campo no Pandapé              | Valor                                                          |
|-------------------------------|----------------------------------------------------------------|
| Nome                          | (qualquer nome descritivo)                                     |
| Tipo de autorização           | **Token dinâmico**                                             |
| URL do token                  | `https://webhook-receiver-v18x.onrender.com/oauth/token`       |
| Client ID                     | valor de `CLIENT_ID` definido no Render                        |
| Client Secret                 | valor de `CLIENT_SECRET` definido no Render                    |
| URL de destino                | `https://webhook-receiver-v18x.onrender.com/webhook/pandape`   |
| Escopo                        | Todas as vagas (ou selecione vagas específicas)                |
| Eventos                       | Selecione os eventos desejados                                 |

> **Como o Pandapé usa o Token Dinâmico:**
> 1. Antes de cada envio, o Pandapé faz `POST /oauth/token` com
>    `Content-Type: application/x-www-form-urlencoded` e os parâmetros
>    `grant_type=client_credentials`, `client_id` e `client_secret`.
> 2. O servidor retorna `{"access_token": "...", "token_type": "Bearer", "expires_in": 3600}`.
> 3. O Pandapé usa esse token no header `Authorization: Bearer <access_token>`
>    ao chamar `/webhook/pandape`.

Use o botão **Testar Webhook** para confirmar a conectividade antes de salvar.

---

## 5. Configure o UptimeRobot (mantém o serviço acordado)

O plano gratuito do Render dorme após 15 min sem requisições. O UptimeRobot
faz um ping a cada 5 min para evitar isso.

1. Crie uma conta gratuita em [uptimerobot.com](https://uptimerobot.com).
2. Clique em **Add New Monitor**:

   | Campo              | Valor                                                    |
   |--------------------|----------------------------------------------------------|
   | Monitor Type       | `HTTP(s)`                                                |
   | Friendly Name      | `Pandape Webhook`                                        |
   | URL                | `https://webhook-receiver-v18x.onrender.com/health`      |
   | Monitoring Interval| `5 minutes`                                              |

3. Clique em **Create Monitor**.

A partir daqui o serviço fica acordado 24/7 e você recebe alertas por e-mail
se ele cair.

---

## 6. Onde ver os webhooks recebidos

Render → seu serviço → aba **Logs**.

Cada webhook aceito aparece assim:

```
============================================================
[2026-06-28 14:32:01] WEBHOOK RECEIVED [PANDAPE]
  Method      : POST
  Content-Type: application/json

  --- Body (JSON) ---
  {
    "event": "candidato.inscrito",
    "candidato": {
      "id": 12345,
      "nome": "João Silva"
    }
  }
============================================================
```

Tentativas rejeitadas também são registradas:
```
[2026-06-28 14:32:01] UNAUTHORIZED - Bearer token invalido, expirado ou ausente
[2026-06-28 14:32:01] TOKEN REQUEST REJECTED - client_id/secret invalidos
```

---

## 7. Variáveis de ambiente — referência

| Variável         | Obrigatória | Padrão (só dev local)           | Descrição                              |
|------------------|-------------|----------------------------------|----------------------------------------|
| `CLIENT_ID`      | Sim (prod)  | `pandape-client-id`              | Identificador enviado pelo Pandapé     |
| `CLIENT_SECRET`  | Sim (prod)  | gerado e salvo em `.client_secret` | Segredo enviado pelo Pandapé         |
| `JWT_SECRET_KEY` | Sim (prod)  | gerado e salvo em `.jwt_secret_key` | Chave de assinatura dos tokens — NUNCA compartilhe |
| `TOKEN_EXPIRES_IN` | Não      | `3600`                           | Validade do token em segundos          |
| `PORT`           | Não         | `5000`                           | Porta (o Render define automaticamente)|

---

## 8. Rodar localmente (opcional)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edite .env com seus valores reais

./start.sh
```

O servidor sobe em `http://localhost:5000`.

### Testar com curl

```bash
# 1. Gerar token
curl -X POST http://localhost:5000/oauth/token \
  -u 'pandape-client-id:pandape-client-secret'

# 2. Enviar webhook
TOKEN="cole_o_access_token_aqui"
curl -X POST http://localhost:5000/webhook/pandape \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event": "candidato.inscrito", "candidato": {"id": 1}}'

# 3. Simular como o Pandapé chama o /oauth/token (form-encoded)
curl -X POST http://localhost:5000/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=pandape-client-id&client_secret=pandape-client-secret"

# 4. Health check
curl http://localhost:5000/health
```

---

## 9. Atualizar o serviço

Qualquer push para `main` no GitHub dispara um redeploy automático no Render:

```bash
git add .
git commit -m "sua mensagem"
git push origin main
```

---

## 10. Troubleshooting

| Sintoma                          | Causa provável                              | Solução                                                   |
|----------------------------------|---------------------------------------------|-----------------------------------------------------------|
| `401` ao gerar token             | `CLIENT_ID`/`CLIENT_SECRET` incorretos       | Confira os valores em Render → Environment                |
| `401` ao receber webhook         | Token expirado ou inválido                  | O Pandapé deve requisitar novo token automaticamente      |
| `404`                            | URL de destino errada                       | Use `/webhook/pandape`, nunca a raiz `/`                  |
| Primeira chamada lenta (~30s)    | Serviço dormindo (plano free)               | Configure o UptimeRobot (passo 5)                         |
| Build falha no Render            | Problema em `requirements.txt`              | Verifique os logs de build no Render                      |
