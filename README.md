# Viva Plena

Projeto acadêmico de TCC voltado para organização de informações clínicas em ginecologia.

O repositório possui três frentes integradas:

- app mobile da paciente
- área web profissional do CESMAC
- gerenciador web administrativo

## 1. Tecnologias do projeto

- Python
- Django
- Django REST Framework
- PostgreSQL
- Expo / React Native
- Node.js

## 2. O que já está implementado

- cadastro e login por perfil
- upload e consulta de exames
- registro do ciclo menstrual
- histórico médico
- pedidos de acesso entre paciente e profissional
- mensagens seguras
- agendamento de consultas
- FAQ
- logs administrativos
- splash animada do CESMAC CITEC no app mobile

## 3. Requisitos e requerimentos

### 3.1. Requisitos obrigatórios do backend

- Python instalado com `pip`
- ambiente virtual Python (`venv`)
- banco de dados configurado
- dependências de `requirements.txt`

### 3.2. Requisitos obrigatórios do app mobile

- Node.js `>= 20.19.0`
- npm
- dependências de `usuario-mobile/package.json`
- Expo Go no celular ou emulador Android/iOS

### 3.3. Versões validadas neste ambiente

- Python `3.14.3`
- Node.js `20.20.2`
- npm `10.8.2`

### 3.4. Banco de dados

O projeto foi pensado para usar PostgreSQL em desenvolvimento e produção.

Também é possível usar SQLite apenas para ambiente local simples, porque o `settings.py` aceita `DATABASE_URL=sqlite:///db.sqlite3`.

### 3.5. Acesso em rede para o mobile

Se o app for aberto em um celular físico:

- o backend precisa estar rodando com `0.0.0.0:8000`
- a variável `EXPO_PUBLIC_API_URL` precisa apontar para o IP da máquina na rede local

Se o app for aberto em outra rede, use túnel com `ngrok`.

## 4. Estrutura principal do repositório

- `ciclo_saude/`: configuração do Django
- `platform_core/`: models, views, APIs e regras de negócio
- `templates/`: telas web
- `static/`: CSS, JS e ícones
- `media/`: uploads locais
- `usuario-mobile/`: app Expo / React Native da paciente

## 5. Instalação do backend

Os exemplos abaixo usam PowerShell no Windows.

### 5.1. Entrar na pasta do projeto

```powershell
cd C:\Users\Nicollas\Desktop\TCC
```

### 5.2. Criar o ambiente virtual

```powershell
python -m venv .venv
```

### 5.3. Ativar o ambiente virtual

```powershell
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativação:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

### 5.4. Atualizar o `pip`

```powershell
python -m pip install --upgrade pip
```

### 5.5. Instalar as dependências Python

```powershell
python -m pip install -r requirements.txt
```

As dependências atuais do backend são:

- `Django==6.0.1`
- `djangorestframework==3.17.1`
- `psycopg[binary]>=3.2,<4.0`

## 6. Configuração do banco de dados

### 6.1. Opção recomendada: PostgreSQL

Instale o PostgreSQL e garanta que o serviço esteja rodando.

Depois crie um banco e um usuário. Exemplo via `psql`:

```sql
CREATE DATABASE viva_plena;
CREATE USER viva_plena_user WITH PASSWORD 'sua_senha_forte';
GRANT ALL PRIVILEGES ON DATABASE viva_plena TO viva_plena_user;
```

### 6.2. Opção alternativa para ambiente local: SQLite

Se você quiser apenas subir o projeto rapidamente sem instalar PostgreSQL, use:

```env
DATABASE_URL=sqlite:///db.sqlite3
```

## 7. Configuração do arquivo `.env` do backend

### 7.1. Criar o arquivo

```powershell
Copy-Item .env.example .env
```

### 7.2. Variáveis aceitas pelo backend

O projeto aceita duas formas de configurar o banco:

1. `DATABASE_URL`
2. variáveis `POSTGRES_*`

### 7.3. Exemplo recomendado com PostgreSQL

```env
DJANGO_SECRET_KEY=sua-chave-local-forte
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,testserver
DATABASE_URL=postgresql://viva_plena_user:sua_senha_forte@127.0.0.1:5432/viva_plena
DB_CONN_MAX_AGE=60
```

### 7.4. Exemplo local com SQLite

```env
DJANGO_SECRET_KEY=sua-chave-local-forte
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,testserver
DATABASE_URL=sqlite:///db.sqlite3
```

### 7.5. O que cada variável faz

- `DJANGO_SECRET_KEY`: chave secreta do Django
- `DJANGO_DEBUG`: use `1` em desenvolvimento local
- `DJANGO_ALLOWED_HOSTS`: hosts adicionais quando `DEBUG=0`
- `DATABASE_URL`: forma preferida de configurar o banco
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`: fallback se `DATABASE_URL` não for definido
- `DB_CONN_MAX_AGE`: tempo de reutilização da conexão com o banco

## 8. Preparação inicial do backend

### 8.1. Aplicar as migrations

```powershell
python manage.py migrate
```

### 8.2. Popular o banco com dados de demonstração

```powershell
python manage.py seed_demo
```

Esse comando cria ou atualiza:

- 1 conta administrativa
- 1 paciente
- 1 profissional
- sem exames enviados
- sem ciclos menstruais registrados
- sem histórico médico preenchido
- sem pedidos de acesso, consultas, mensagens, FAQ ou logs de demonstração

## 9. Como rodar o backend

### 9.1. Para uso apenas no navegador da própria máquina

```powershell
python manage.py runserver
```

Endereço:

- `http://127.0.0.1:8000/`

### 9.2. Para testar o app mobile em celular físico na mesma rede

```powershell
python manage.py runserver 0.0.0.0:8000
```

Com isso, o backend fica acessível pela rede local.

## 10. Rotas web principais

- página inicial: `http://127.0.0.1:8000/`
- login web: `http://127.0.0.1:8000/entrar/`
- portal profissional: `http://127.0.0.1:8000/profissional/`
- gerenciador administrativo: `http://127.0.0.1:8000/gerenciador/`
- área informativa da paciente na web: `http://127.0.0.1:8000/paciente/`

Rotas antigas como `/mobile/` e `/clinica/` continuam funcionando com redirecionamento.

## 11. Instalação do app mobile

### 11.1. Entrar na pasta do app

```powershell
cd usuario-mobile
```

### 11.2. Instalar as dependências JavaScript

```powershell
npm install
```

### 11.3. Criar o arquivo `.env` do mobile

```powershell
Copy-Item .env.example .env
```

### 11.4. Configurar a URL do backend

O app usa `EXPO_PUBLIC_API_URL`.

Exemplos:

- navegador e backend na mesma máquina: `http://127.0.0.1:8000`
- Android Emulator: `http://10.0.2.2:8000`
- celular físico na mesma rede: `http://SEU-IP-LOCAL:8000`

Exemplo real:

```env
EXPO_PUBLIC_API_URL=http://192.168.0.15:8000
```

Importante:

- `127.0.0.1` funciona para testes locais na própria máquina
- `127.0.0.1` não funciona em celular físico conectado por Wi-Fi
- para celular físico, rode o Django com `0.0.0.0:8000`

## 12. Como rodar o app mobile

### 12.1. Inicialização padrão

```powershell
npx expo start
```

### 12.2. Abrir direto no Android

```powershell
npm run android
```

### 12.3. Abrir direto no iOS

```powershell
npm run ios
```

## 13. Uso do app mobile em redes diferentes

### 13.1. Túnel automático com ngrok

Antes de rodar esse modo, defina `NGROK_AUTHTOKEN`.

Exemplo no Windows:

```powershell
[Environment]::SetEnvironmentVariable("NGROK_AUTHTOKEN", "SEU_TOKEN_AQUI", "User")
```

Depois rode:

```powershell
npm run start:tunnel
```

Esse script:

- encerra processos antigos do Expo e ngrok
- limpa variáveis de proxy
- cria uma URL pública
- sobe o Expo na porta `8082`
- injeta `EXPO_PACKAGER_PROXY_URL` automaticamente

### 13.2. Fallback manual com URL pública pronta

```powershell
npm run start:public-url -- https://SEU-URL-PUBLICO
```

Use sempre a URL pública que estiver apontando para `http://localhost:8082`.

## 14. Ordem recomendada da primeira execução

Se for a sua primeira vez rodando tudo, siga esta ordem:

1. instalar Python
2. criar e ativar `.venv`
3. instalar dependências do backend
4. instalar e configurar o banco
5. criar `.env` do backend
6. rodar `python manage.py migrate`
7. rodar `python manage.py seed_demo`
8. subir o backend com `python manage.py runserver` ou `python manage.py runserver 0.0.0.0:8000`
9. entrar em `usuario-mobile`
10. rodar `npm install`
11. criar `usuario-mobile/.env`
12. ajustar `EXPO_PUBLIC_API_URL`
13. rodar `npx expo start`

## 15. Contas de teste

As contas abaixo são criadas por `python manage.py seed_demo`:

- Admin: `admin@vivaplena.local` / `Admin12345`
- Paciente: `maria@demo.com` / `Paciente123`
- Profissional: `helena@demo.com` / `Clinica123`

Uso esperado de cada conta:

- Admin: acessar pelo gerenciador web
- Profissional: acessar pela área web profissional
- Paciente: acessar principalmente pelo app mobile

## 16. Comandos úteis

### Backend

```powershell
python manage.py migrate
python manage.py seed_demo
python manage.py test
python manage.py runserver
python manage.py runserver 0.0.0.0:8000
```

### Mobile

```powershell
npm install
npx expo start
npm run android
npm run ios
npm run start:tunnel
npm run start:public-url -- https://SEU-URL-PUBLICO
npm run lint
```

## 17. Problemas comuns e como resolver

### 17.1. `ModuleNotFoundError: No module named 'django'`

Normalmente significa que:

- a `.venv` não foi ativada
- as dependências não foram instaladas

Solução:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 17.2. Erro de conexão com PostgreSQL

Verifique:

- se o serviço do PostgreSQL está rodando
- se o banco foi criado
- se o usuário e a senha no `.env` estão corretos
- se a porta configurada é mesmo `5432` ou outra porta usada na sua máquina

### 17.3. O app mobile abre, mas não conecta com o backend

Verifique:

- se o Django está rodando
- se a `EXPO_PUBLIC_API_URL` está correta
- se você usou o IP da máquina, e não `127.0.0.1`, quando estiver em celular físico
- se o backend foi iniciado com `python manage.py runserver 0.0.0.0:8000`

### 17.4. `NGROK_AUTHTOKEN nao encontrado`

Defina a variável e rode novamente:

```powershell
[Environment]::SetEnvironmentVariable("NGROK_AUTHTOKEN", "SEU_TOKEN_AQUI", "User")
```

### 17.5. PowerShell bloqueia a ativação da `.venv`

Use:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

## 18. O que não deve ser enviado para o GitHub

- `.env`
- `.venv`
- `node_modules`
- `.expo`
- logs
- caches
- arquivos temporários
- uploads locais em `media/`
- artefatos de build

## 19. Observações finais

- o backend usa um banco temporário em memória para testes quando nenhuma configuração externa é informada e o comando executado é `python manage.py test`
- o comando `seed_demo` pode ser executado novamente para restaurar apenas as contas demo principais e suas senhas, sem dados clínicos preenchidos
- o app mobile possui um `README` próprio em [`usuario-mobile/README.md`](usuario-mobile/README.md), mas o fluxo completo do projeto está documentado neste arquivo principal
