import json
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from urllib import error, parse, request


def normalize_url(url):
    return url.strip().rstrip("/")


def normalize_error_message(detail):
    if isinstance(detail, dict):
        if "detail" in detail:
            return str(detail["detail"])
        return "\n".join(f"{key}: {value}" for key, value in detail.items())
    if isinstance(detail, list):
        return "\n".join(str(item) for item in detail)
    return str(detail)


CLINIC_FIELD_LABELS = {
    "trade_name": "Nome fantasia",
    "company_name": "Razao social",
    "email": "E-mail",
    "password": "Senha",
    "cnpj": "CNPJ",
    "phone_primary": "Telefone principal",
    "technical_manager": "Responsavel tecnico",
    "crm": "CRM",
    "city": "Cidade",
    "state": "Estado",
}

CLINIC_DASHBOARD_LABELS = {
    "approved_count": "Pacientes autorizadas",
    "pending_count": "Solicitacoes em aberto",
    "exam_count": "Exames disponiveis",
}

CLINIC_REPORT_LABELS = {
    "approved_count": "Pacientes com acesso aprovado",
    "exams_count": "Exames disponiveis",
    "appointments_count": "Consultas",
}

CLINIC_EMPTY_STATES = {
    "requests": ("Nenhuma solicitacao registrada.", "-", "-"),
    "exams": ("Nenhum exame liberado.", "-", "-", "-", "-"),
    "messages": ("Nenhuma mensagem encontrada.", "-", "-", "-"),
}


class ApiClient:
    def __init__(self):
        self.base_url = ""
        self.token = None

    def configure(self, base_url):
        self.base_url = normalize_url(base_url)

    def _headers(self, is_json=True):
        headers = {"Accept": "application/json"}
        if is_json:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Token {self.token}"
        return headers

    def request(self, path, method="GET", data=None, is_json=True):
        payload = None
        if data is not None:
            payload = json.dumps(data).encode("utf-8") if is_json else data

        req = request.Request(
            f"{self.base_url}{path}",
            data=payload,
            method=method,
            headers=self._headers(is_json=is_json),
        )
        try:
            with request.urlopen(req) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8"))
            except Exception:
                detail = exc.reason
            raise RuntimeError(normalize_error_message(detail))
        except error.URLError as exc:
            raise RuntimeError(str(exc.reason))

    def login(self, base_url, email, password):
        self.configure(base_url)
        data = self.request("/api/auth/token/", method="POST", data={"email": email, "password": password})
        self.token = data["token"]
        return data["user"]

    def register_clinic(self, base_url, payload):
        self.configure(base_url)
        return self.request("/api/auth/register/clinic/", method="POST", data=payload)

    def logout(self):
        if self.token and self.base_url:
            try:
                self.request("/api/auth/logout/", method="POST", data={})
            except RuntimeError:
                pass
        self.token = None


class ClinicDesktopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ciclo & Saude - Aplicativo da Clinica")
        self.geometry("1180x760")
        self.minsize(1080, 700)
        self.configure(bg="#eef3f8")

        self.api = ApiClient()
        self.user = None

        self.login_frame = LoginFrame(self, self.handle_login, self.handle_register)
        self.login_frame.pack(fill="both", expand=True)

        self.app_frame = None

    def run_in_thread(self, callback, on_success=None):
        def worker():
            try:
                result = callback()
                if on_success:
                    self.after(0, lambda: on_success(result))
            except Exception as exc:
                error_message = str(exc)
                self.after(0, lambda message=error_message: messagebox.showerror("Erro", message))

        threading.Thread(target=worker, daemon=True).start()

    def handle_login(self, base_url, email, password):
        self.run_in_thread(lambda: self.api.login(base_url, email, password), self.finish_login)

    def handle_register(self, payload):
        self.run_in_thread(
            lambda: self.api.register_clinic(payload["base_url"], payload["data"]),
            lambda _: messagebox.showinfo("Cadastro enviado", "Clinica cadastrada. Aguarde aprovacao no gerenciador web."),
        )

    def finish_login(self, user):
        self.user = user
        self.login_frame.pack_forget()
        if self.app_frame:
            self.app_frame.destroy()
        self.app_frame = MainClinicFrame(self, self.api, self.user, self.logout)
        self.app_frame.pack(fill="both", expand=True)

    def logout(self):
        self.api.logout()
        self.user = None
        if self.app_frame:
            self.app_frame.destroy()
            self.app_frame = None
        self.login_frame.pack(fill="both", expand=True)


class LoginFrame(tk.Frame):
    def __init__(self, master, on_login, on_register):
        super().__init__(master, bg="#eef3f8")
        self.on_login = on_login
        self.on_register = on_register

        wrapper = tk.Frame(self, bg="#eef3f8")
        wrapper.place(relx=0.5, rely=0.5, anchor="center")

        hero = tk.Frame(wrapper, bg="#123969", padx=32, pady=32)
        hero.grid(row=0, column=0, sticky="nsew")
        form = tk.Frame(wrapper, bg="white", padx=32, pady=32)
        form.grid(row=0, column=1, sticky="nsew")

        tk.Label(hero, text="Ciclo & Saude", fg="white", bg="#123969", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(hero, text="Area operacional da clinica parceira", fg="#dce8ff", bg="#123969", font=("Segoe UI", 12)).pack(anchor="w", pady=(8, 24))
        tk.Label(hero, text="Solicite acessos, acompanhe exames liberados, troque mensagens seguras e consulte indicadores sem depender do navegador.", fg="white", bg="#123969", wraplength=320, justify="left", font=("Segoe UI", 11)).pack(anchor="w")

        tk.Label(form, text="Acessar area da clinica", bg="white", fg="#162033", font=("Segoe UI", 20, "bold")).pack(anchor="w")

        self.base_url = tk.StringVar(value="http://127.0.0.1:8000")
        self.email = tk.StringVar(value="clinica@demo.com")
        self.password = tk.StringVar(value="Clinica123")

        self._entry(form, "URL do backend", self.base_url)
        self._entry(form, "E-mail", self.email)
        self._entry(form, "Senha", self.password, show="*")

        ttk.Button(form, text="Acessar sistema", command=self.submit_login).pack(fill="x", pady=(18, 10))
        ttk.Button(form, text="Solicitar cadastro", command=self.open_register_dialog).pack(fill="x")

    def _entry(self, parent, label, variable, show=None):
        tk.Label(parent, text=label, bg="white", fg="#516274", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(18, 4))
        ttk.Entry(parent, textvariable=variable, show=show, width=34).pack(fill="x")

    def submit_login(self):
        self.on_login(self.base_url.get(), self.email.get(), self.password.get())

    def open_register_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Solicitar cadastro da clinica")
        dialog.geometry("420x520")
        dialog.configure(bg="white")

        fields = {
            "trade_name": tk.StringVar(),
            "company_name": tk.StringVar(),
            "email": tk.StringVar(),
            "password": tk.StringVar(),
            "cnpj": tk.StringVar(),
            "phone_primary": tk.StringVar(),
            "technical_manager": tk.StringVar(),
            "crm": tk.StringVar(),
            "city": tk.StringVar(),
            "state": tk.StringVar(),
        }

        frame = tk.Frame(dialog, bg="white", padx=24, pady=24)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="Cadastro institucional", bg="white", fg="#162033", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(frame, text="Preencha os dados da clinica para enviar a solicitacao de aprovacao.", bg="white", fg="#5c6d86", wraplength=340, justify="left", font=("Segoe UI", 10)).pack(anchor="w", pady=(6, 4))

        for key, variable in fields.items():
            tk.Label(frame, text=CLINIC_FIELD_LABELS.get(key, key.replace("_", " ").title()), bg="white", fg="#516274", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 4))
            ttk.Entry(frame, textvariable=variable, show="*" if key == "password" else None).pack(fill="x")

        def submit():
            self.on_register({
                "base_url": self.base_url.get(),
                "data": {key: value.get() for key, value in fields.items()},
            })
            dialog.destroy()

        ttk.Button(frame, text="Enviar solicitacao", command=submit).pack(fill="x", pady=20)


class MainClinicFrame(tk.Frame):
    def __init__(self, master, api, user, on_logout):
        super().__init__(master, bg="#eef3f8")
        self.api = api
        self.user = user
        self.on_logout = on_logout

        sidebar = tk.Frame(self, bg="#17243b", width=240)
        sidebar.pack(side="left", fill="y")
        content = tk.Frame(self, bg="#eef3f8")
        content.pack(side="right", fill="both", expand=True)

        tk.Label(sidebar, text="Clinica parceira", fg="white", bg="#17243b", font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=18, pady=(24, 6))
        tk.Label(sidebar, text=user["full_name"], fg="#d6e1f5", bg="#17243b", font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(0, 24))

        ttk.Button(sidebar, text="Atualizar painel", command=self.refresh_all).pack(fill="x", padx=18, pady=6)
        ttk.Button(sidebar, text="Encerrar sessao", command=self.on_logout).pack(fill="x", padx=18, pady=6)

        header = tk.Frame(content, bg="white", padx=20, pady=16)
        header.pack(fill="x", padx=16, pady=16)
        tk.Label(header, text="Central da clinica", bg="white", fg="#162033", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(header, text="A operacao acontece por integracao direta com a API do sistema, com foco em acesso autorizado e rastreabilidade.", bg="white", fg="#5c6d86", font=("Segoe UI", 10)).pack(anchor="w")

        self.notebook = ttk.Notebook(content)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.dashboard_tab = DashboardTab(self.notebook, self.api)
        self.requests_tab = RequestsTab(self.notebook, self.api)
        self.exams_tab = ExamsTab(self.notebook, self.api)
        self.messages_tab = MessagesTab(self.notebook, self.api)
        self.reports_tab = ReportsTab(self.notebook, self.api)

        self.notebook.add(self.dashboard_tab, text="Painel inicial")
        self.notebook.add(self.requests_tab, text="Solicitacoes")
        self.notebook.add(self.exams_tab, text="Exames liberados")
        self.notebook.add(self.messages_tab, text="Mensagens")
        self.notebook.add(self.reports_tab, text="Indicadores")

        self.refresh_all()

    def refresh_all(self):
        for tab in [self.dashboard_tab, self.requests_tab, self.exams_tab, self.messages_tab, self.reports_tab]:
            tab.refresh()


class BaseTab(ttk.Frame):
    def __init__(self, master, api):
        super().__init__(master)
        self.api = api

    def async_call(self, callback, on_success):
        def worker():
            try:
                result = callback()
                self.after(0, lambda: on_success(result))
            except Exception as exc:
                error_message = str(exc)
                self.after(0, lambda message=error_message: messagebox.showerror("Erro", message))

        threading.Thread(target=worker, daemon=True).start()


class DashboardTab(BaseTab):
    def __init__(self, master, api):
        super().__init__(master, api)
        self.cards = {}
        top = ttk.Frame(self, padding=16)
        top.pack(fill="x")
        for label in ["approved_count", "pending_count", "exam_count"]:
            card = ttk.LabelFrame(top, text=CLINIC_DASHBOARD_LABELS[label], padding=18)
            card.pack(side="left", fill="x", expand=True, padx=6)
            value = ttk.Label(card, text="0", font=("Segoe UI", 20, "bold"))
            value.pack()
            self.cards[label] = value

    def refresh(self):
        self.async_call(lambda: self.api.request("/api/clinic/dashboard/"), self.render)

    def render(self, data):
        self.cards["approved_count"].config(text=str(data.get("approved_count", 0)))
        self.cards["pending_count"].config(text=str(data.get("pending_count", 0)))
        self.cards["exam_count"].config(text=str(data.get("exam_count", 0)))


class RequestsTab(BaseTab):
    def __init__(self, master, api):
        super().__init__(master, api)
        wrapper = ttk.Frame(self, padding=16)
        wrapper.pack(fill="both", expand=True)

        form = ttk.LabelFrame(wrapper, text="Novo pedido de acesso", padding=16)
        form.pack(fill="x")
        self.patient_cpf = tk.StringVar()
        self.request_note = tk.StringVar()
        ttk.Label(form, text="CPF da paciente").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.patient_cpf, width=20).grid(row=1, column=0, sticky="ew", padx=(0, 12))
        ttk.Label(form, text="Observacao interna").grid(row=0, column=1, sticky="w")
        ttk.Entry(form, textvariable=self.request_note).grid(row=1, column=1, sticky="ew")
        ttk.Button(form, text="Enviar pedido", command=self.submit_request).grid(row=1, column=2, padx=(12, 0))
        form.columnconfigure(1, weight=1)

        self.tree = ttk.Treeview(wrapper, columns=("patient", "status", "date"), show="headings")
        for col, text in [("patient", "Paciente"), ("status", "Status"), ("date", "Solicitado em")]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=180 if col != "date" else 140)
        self.tree.pack(fill="both", expand=True, pady=(16, 0))

    def submit_request(self):
        data = {"patient_cpf": self.patient_cpf.get(), "request_note": self.request_note.get()}
        self.async_call(
            lambda: self.api.request("/api/clinic/access-requests/", method="POST", data=data),
            lambda _: [self.patient_cpf.set(""), self.request_note.set(""), self.refresh(), messagebox.showinfo("Sucesso", "Pedido de acesso enviado com sucesso.")],
        )

    def refresh(self):
        self.async_call(lambda: self.api.request("/api/clinic/access-requests/"), self.render)

    def render(self, items):
        for row in self.tree.get_children():
            self.tree.delete(row)
        if not items:
            self.tree.insert("", "end", values=CLINIC_EMPTY_STATES["requests"])
            return
        for item in items:
            self.tree.insert("", "end", values=(item["patient"]["full_name"], item["status_label"], item["requested_at"][:16].replace("T", " ")))


class ExamsTab(BaseTab):
    def __init__(self, master, api):
        super().__init__(master, api)
        wrapper = ttk.Frame(self, padding=16)
        wrapper.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrapper, columns=("patient", "title", "type", "date", "url"), show="headings")
        for col, text in [("patient", "Paciente"), ("title", "Exame"), ("type", "Categoria"), ("date", "Data"), ("url", "Arquivo")]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=170)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.open_selected)

    def refresh(self):
        self.async_call(lambda: self.api.request("/api/clinic/exams/"), self.render)

    def render(self, items):
        for row in self.tree.get_children():
            self.tree.delete(row)
        if not items:
            self.tree.insert("", "end", values=CLINIC_EMPTY_STATES["exams"])
            return
        for item in items:
            self.tree.insert("", "end", values=(item["owner"]["full_name"] if "owner" in item else "-", item["title"], item["exam_type"], item["performed_at"], item.get("file_url", "")))

    def open_selected(self, _event):
        current = self.tree.focus()
        if not current:
            return
        values = self.tree.item(current, "values")
        if values and values[4]:
            webbrowser.open(values[4])
        else:
            messagebox.showinfo("Arquivo indisponivel", "Nao ha um arquivo associado a este registro.")


class MessagesTab(BaseTab):
    def __init__(self, master, api):
        super().__init__(master, api)
        wrapper = ttk.Frame(self, padding=16)
        wrapper.pack(fill="both", expand=True)

        form = ttk.LabelFrame(wrapper, text="Nova mensagem segura", padding=16)
        form.pack(fill="x")
        self.recipient_id = tk.StringVar()
        self.message_body = tk.StringVar()
        ttk.Label(form, text="ID da paciente").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.recipient_id, width=18).grid(row=1, column=0, sticky="ew", padx=(0, 12))
        ttk.Label(form, text="Conteudo da mensagem").grid(row=0, column=1, sticky="w")
        ttk.Entry(form, textvariable=self.message_body).grid(row=1, column=1, sticky="ew")
        ttk.Button(form, text="Enviar mensagem", command=self.submit_message).grid(row=1, column=2, padx=(12, 0))
        form.columnconfigure(1, weight=1)

        self.tree = ttk.Treeview(wrapper, columns=("from", "to", "body", "created"), show="headings")
        for col, text in [("from", "Enviado por"), ("to", "Enviado para"), ("body", "Conteudo"), ("created", "Data")]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=180)
        self.tree.pack(fill="both", expand=True, pady=(16, 0))

    def submit_message(self):
        data = {"recipient_id": self.recipient_id.get(), "body": self.message_body.get()}
        self.async_call(
            lambda: self.api.request("/api/clinic/messages/", method="POST", data=data),
            lambda _: [self.recipient_id.set(""), self.message_body.set(""), self.refresh(), messagebox.showinfo("Sucesso", "Mensagem enviada com sucesso.")],
        )

    def refresh(self):
        self.async_call(lambda: self.api.request("/api/clinic/messages/"), self.render)

    def render(self, items):
        for row in self.tree.get_children():
            self.tree.delete(row)
        if not items:
            self.tree.insert("", "end", values=CLINIC_EMPTY_STATES["messages"])
            return
        for item in items:
            self.tree.insert("", "end", values=(item["sender"]["full_name"], item["recipient"]["full_name"], item["body"], item["created_at"][:16].replace("T", " ")))


class ReportsTab(BaseTab):
    def __init__(self, master, api):
        super().__init__(master, api)
        self.labels = {}
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Visao consolidada dos principais indicadores operacionais da clinica.", font=("Segoe UI", 10), foreground="#5c6d86").pack(anchor="w", pady=(0, 8))
        for label in ["approved_count", "exams_count", "appointments_count"]:
            box = ttk.LabelFrame(frame, text=CLINIC_REPORT_LABELS[label], padding=20)
            box.pack(fill="x", pady=8)
            value = ttk.Label(box, text="0", font=("Segoe UI", 20, "bold"))
            value.pack(anchor="w")
            self.labels[label] = value

    def refresh(self):
        self.async_call(lambda: self.api.request("/api/clinic/reports/"), self.render)

    def render(self, data):
        for key, label in self.labels.items():
            label.config(text=str(data.get(key, 0)))


if __name__ == "__main__":
    app = ClinicDesktopApp()
    app.mainloop()
