#!/bin/sh
# Executado pelo serviço n8n-importar a cada "docker compose up":
# 1) cria/atualiza a credencial SMTP do Gmail a partir do .env (GMAIL_USUARIO e GMAIL_SENHA_APP);
# 2) importa os workflows de /workflows e os ativa.
set -e

node -e '
const fs = require("fs");
const credencial = [{
  id: "LitMonitorGmail01",
  name: "Gmail (Litigation Monitor)",
  type: "smtp",
  data: {
    user: (process.env.GMAIL_USUARIO || "").trim(),
    password: (process.env.GMAIL_SENHA_APP || "").replace(/\s/g, ""),
    host: "smtp.gmail.com",
    port: 465,
    secure: true
  }
}];
fs.writeFileSync("/tmp/credencial-gmail.json", JSON.stringify(credencial));
'
if n8n import:credentials --input=/tmp/credencial-gmail.json; then
  echo "Credencial do Gmail importada."
else
  echo "AVISO: não foi possível importar a credencial do Gmail. Crie uma credencial SMTP no n8n (veja o README)."
fi
rm -f /tmp/credencial-gmail.json

n8n import:workflow --separate --input=/workflows
n8n update:workflow --all --active=true
