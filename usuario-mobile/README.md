# App Mobile da Paciente

Aplicativo em Expo/React Native que consome a API do projeto.

## Como rodar

```powershell
npm install
npx expo start
```

## Usar em redes diferentes

```powershell
npm run start:tunnel
```

Esse comando:

- limpa processos antigos do `ngrok` e do Metro nas portas `8081` e `8082`
- usa o SDK oficial moderno do ngrok com `NGROK_AUTHTOKEN`
- cria uma URL publica automaticamente
- inicia o Expo com `EXPO_PACKAGER_PROXY_URL` apontando para essa URL

## Fallback manual

Se quiser usar um tunel externo manualmente:

```powershell
ngrok http 8082
npm run start:public-url -- https://SEU-URL-PUBLICO
```

Use sempre a URL `https://...` que estiver encaminhando para `http://localhost:8082`.

## Requisitos

- Node 20 ou superior
- backend Django rodando

## O que tem hoje

- login e cadastro
- exames
- ciclo menstrual
- historico medico
- consultas
- mensagens
- notificacoes

## Conta de teste

Criada por `python manage.py seed_demo`:

- `maria@demo.com`
- `Paciente123`

## Observacao

`node_modules` e `.expo` sao locais e nao devem ser enviados para o GitHub.
