# Ciclo & Saude

Projeto academico de TCC para organizar informacoes clinicas em ginecologia.

O sistema tem 3 partes:

- app mobile da usuaria
- aplicativo desktop da clinica
- gerenciador web administrativo

## Tecnologias

- Python
- Django
- Django REST Framework
- SQLite
- Expo/React Native
- Tkinter

## Funcionalidades atuais

- cadastro e login por perfil
- exames
- ciclo menstrual
- historico medico
- pedidos de acesso entre paciente e clinica
- mensagens
- consultas pela usuaria
- FAQ e logs no painel web

## Como rodar

### Backend

```powershell
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Depois abra `http://127.0.0.1:8000/`.

### Mobile

```powershell
cd usuario-mobile
npm install
npx expo start
```

### Desktop da clinica

```powershell
cd clinica-desktop
python app.py
```

## Contas de teste

- Admin: `admin@ciclosaude.local` / `Admin12345`
- Paciente: `maria@demo.com` / `Paciente123`
- Clinica: `clinica@demo.com` / `Clinica123`

## Observacao

O banco atual e SQLite e foi mantido assim para desenvolvimento e apresentacao.
