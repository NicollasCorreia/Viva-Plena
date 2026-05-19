from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import AccessRequest, Appointment, FAQ, SecureMessage, User


class BootstrapFormMixin:
    def apply_bootstrap(self):
        for field in self.fields.values():
            widget = field.widget
            css_class = "form-control"
            if isinstance(widget, forms.Select):
                css_class = "form-select"
            elif isinstance(widget, forms.CheckboxInput):
                css_class = "form-check-input"
            elif isinstance(widget, forms.ClearableFileInput):
                css_class = "form-control"

            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {css_class}".strip()

    def configure_field(self, field_name, *, label=None, placeholder=None, help_text=None, widget_attrs=None):
        field = self.fields[field_name]
        if label is not None:
            field.label = label
        if help_text is not None:
            field.help_text = help_text
        if placeholder is not None:
            field.widget.attrs["placeholder"] = placeholder
        if widget_attrs:
            field.widget.attrs.update(widget_attrs)


class EmailAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"placeholder": "nome@exemplo.com"}))
    password = forms.CharField(label="Senha", strip=False, widget=forms.PasswordInput(attrs={"placeholder": "Digite sua senha"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.configure_field("username", label="E-mail", placeholder="nome@exemplo.com")
        self.configure_field("password", label="Senha", placeholder="Digite sua senha")


class ClinicRegistrationForm(BootstrapFormMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = [
            "full_name",
            "email",
            "phone_primary",
            "crm",
            "specialty",
            "city",
            "state",
        ]
        labels = {
            "full_name": "Nome completo",
            "email": "E-mail",
            "phone_primary": "Telefone",
            "crm": "CRM",
            "specialty": "Especialidade",
            "city": "Cidade",
            "state": "UF",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.configure_field("full_name", placeholder="Nome da profissional")
        self.configure_field("email", placeholder="nome@cesmac.edu.br")
        self.configure_field("phone_primary", placeholder="(11) 99999-0000")
        self.configure_field("crm", placeholder="Ex.: CRM-AL 12345")
        self.configure_field("specialty", placeholder="Ex.: Ginecologia e obstetrícia")
        self.configure_field("city", placeholder="Cidade")
        self.configure_field("state", placeholder="UF", widget_attrs={"maxlength": 2})
        self.configure_field(
            "password1",
            label="Crie uma senha",
            placeholder="Use pelo menos 8 caracteres",
            help_text="Escolha uma senha com pelo menos 8 caracteres para proteger seu acesso web profissional.",
        )
        self.configure_field(
            "password2",
            label="Confirme sua senha",
            placeholder="Repita a senha",
            help_text="Digite a mesma senha novamente para confirmar.",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CLINIC
        user.full_name = self.cleaned_data["full_name"]
        user.trade_name = self.cleaned_data["full_name"]
        user.company_name = "CESMAC"
        user.technical_manager = self.cleaned_data["full_name"]
        user.institution_name = "CESMAC"
        user.approval_status = User.ApprovalStatus.PENDING
        user.is_active = True
        user.username = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class AdminCreationForm(BootstrapFormMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["full_name", "email"]
        labels = {
            "full_name": "Nome completo",
            "email": "E-mail",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.configure_field("full_name", placeholder="Nome da administradora")
        self.configure_field("email", placeholder="admin@vivaplena.local")
        self.configure_field(
            "password1",
            label="Crie uma senha",
            placeholder="Use pelo menos 8 caracteres",
            help_text="Defina uma senha forte para o novo acesso administrativo.",
        )
        self.configure_field(
            "password2",
            label="Confirme sua senha",
            placeholder="Repita a senha",
            help_text="Repita a senha para confirmar a criação da conta.",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.ADMIN
        user.full_name = self.cleaned_data["full_name"]
        user.approval_status = User.ApprovalStatus.APPROVED
        user.is_active = True
        user.is_staff = True
        user.is_superuser = False
        user.username = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class AccessRequestForm(BootstrapFormMixin, forms.Form):
    patient_cpf = forms.CharField(label="CPF da paciente", max_length=14)
    request_note = forms.CharField(label="Mensagem para a paciente", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.configure_field("patient_cpf", placeholder="000.000.000-00")
        self.configure_field("request_note", placeholder="Explique, se quiser, por que você precisa desse acesso.")


class ClinicAppointmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["patient", "specialist", "scheduled_for"]
        labels = {
            "patient": "Paciente",
            "specialist": "Especialidade ou tipo de atendimento",
            "scheduled_for": "Data e horário",
        }
        widgets = {"scheduled_for": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        clinic = kwargs.pop("clinic", None)
        super().__init__(*args, **kwargs)
        if clinic:
            approved_patient_ids = clinic.clinic_requests.filter(
                status=AccessRequest.Status.APPROVED
            ).values_list("patient_id", flat=True)
            self.fields["patient"].queryset = User.objects.filter(id__in=approved_patient_ids)
        
        self.apply_bootstrap()
        self.configure_field("specialist", placeholder="Ex.: Retorno, Exame Clínico, Coleta")

    def clean_scheduled_for(self):
        scheduled_for = self.cleaned_data["scheduled_for"]
        if scheduled_for <= timezone.now():
            raise ValidationError("Escolha uma data e um horário futuros para a consulta.")
        return scheduled_for


class SecureMessageForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SecureMessage
        fields = ["recipient", "body"]
        labels = {"recipient": "Destinatária", "body": "Mensagem"}
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Escreva sua mensagem de forma clara e objetiva."})}

    def __init__(self, *args, **kwargs):
        allowed_recipients = kwargs.pop("allowed_recipients", User.objects.none())
        super().__init__(*args, **kwargs)
        self.fields["recipient"].queryset = allowed_recipients
        self.apply_bootstrap()
        self.configure_field("recipient", label="Para quem você quer enviar")


class FAQForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FAQ
        fields = ["question", "answer", "is_active"]
        labels = {
            "question": "Pergunta",
            "answer": "Resposta",
            "is_active": "Mostrar esta pergunta na área de ajuda",
        }
        widgets = {"answer": forms.Textarea(attrs={"rows": 4, "placeholder": "Escreva a resposta de um jeito simples e útil para quem vai ler."})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
        self.configure_field("question", placeholder="Ex.: Como libero meus exames para uma profissional?")
