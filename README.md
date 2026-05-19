# Viva Plena

Projeto academico desenvolvido como TCC, com foco na organizacao de informacoes clinicas em ginecologia.

O sistema esta dividido em tres frentes:

- app da paciente
- area web profissional do CESMAC
- gerenciador web administrativo

## Tecnologias utilizadas

- Python
- Django
- Django REST Framework
- PostgreSQL
- Expo/React Native

## O que ja esta implementado

- cadastro e login por perfil
- upload e consulta de exames
- registro do ciclo menstrual
- historico medico
- pedidos de acesso entre paciente e profissional
- mensagens seguras entre paciente e profissional
- agendamento de consultas pela usuaria
- FAQ e logs no painel web

## Como executar

### 1. Dependencias

```powershell
python -m pip install -r requirements.txt
```

### 2. Ambiente local

Crie um arquivo `.env` a partir do exemplo:

```powershell
Copy-Item .env.example .env
```

Depois, ajuste os valores locais. O backend aceita `DATABASE_URL` ou as variaveis `POSTGRES_*`.

Exemplo minimo:

```env
DJANGO_SECRET_KEY=<sua-chave-local>
DJANGO_DEBUG=1
DATABASE_URL=postgresql://DB_USER:DB_PASSWORD@127.0.0.1:5432/DB_NAME
```

### 3. Backend

```powershell
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Depois, abra `http://127.0.0.1:8000/`.

### 4. Rotas web principais

- Paciente: `http://127.0.0.1:8000/paciente/`
- Profissional: `http://127.0.0.1:8000/profissional/`
- Gerenciador: `http://127.0.0.1:8000/gerenciador/`

Rotas antigas como `/mobile/` e `/clinica/` continuam funcionando por redirecionamento.

### 5. App mobile

```powershell
cd usuario-mobile
npm install
npx expo start
```

Para testar no celular, a API deve apontar para o IP da maquina ou para um tunel.

## Contas de teste

As contas abaixo sao criadas por `python manage.py seed_demo`:

- Admin: `admin@vivaplena.local` / `Admin12345`
- Paciente: `maria@demo.com` / `Paciente123`
- Profissional: `helena@demo.com` / `Clinica123`

## O que nao vai para o GitHub

- `.env`, `.venv`, `node_modules`, `.expo`, logs, caches e arquivos temporarios locais
- uploads em `media/` e saidas de build
- banco preenchido e dependencias instaladas localmente

## Observacoes

- Para `python manage.py test`, o projeto usa um banco temporario em memoria quando nenhuma configuracao externa e informada.
- Os dados de exemplo podem ser recriados com `python manage.py seed_demo`.
