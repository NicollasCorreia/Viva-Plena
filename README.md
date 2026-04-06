# Ciclo & Saúde

Projeto acadêmico desenvolvido como TCC, com foco na organização de informações clínicas em ginecologia.

O sistema foi dividido em três partes:

- app mobile da usuária
- aplicativo desktop da clínica
- gerenciador web administrativo

## Tecnologias utilizadas

- Python
- Django
- Django REST Framework
- SQLite
- Expo/React Native
- Tkinter

## O que já está implementado

- cadastro e login por perfil
- upload e consulta de exames
- registro do ciclo menstrual
- histórico médico
- pedidos de acesso entre paciente e clínica
- mensagens entre paciente e clínica
- agendamento de consultas pela usuária
- FAQ e logs no painel web

## Como executar

### Backend

```powershell
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Depois, abra `http://127.0.0.1:8000/`.

### App mobile

```powershell
cd usuario-mobile
npm install
npx expo start
```

Se for testar no celular, use o IP da máquina no endereço da API.

### Aplicativo desktop da clínica

```powershell
cd clinica-desktop
python app.py
```

## Contas de teste

- Admin: `admin@ciclosaude.local` / `Admin12345`
- Paciente: `maria@demo.com` / `Paciente123`
- Clínica: `clinica@demo.com` / `Clinica123`

## Observações

- O projeto usa SQLite neste momento, por ser mais simples para desenvolvimento e demonstração.
- Os dados de exemplo podem ser carregados com `python manage.py seed_demo`.
- O repositório não inclui o banco preenchido nem dependências instaladas localmente.
