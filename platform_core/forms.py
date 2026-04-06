from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import AccessRequest, Appointment, CycleRecord, Exam, FAQ, MedicalHistory, SecureMessage, User


class BootstrapFormMixin:
    def apply_bootstrap(self):
        for field in self.fields.values():
            widget = field.widget
            css_class = "form-control"
            if isinstance(widget, (forms.Select,)):
                css_class = "form-select"
            elif isinstance(widget, (forms.CheckboxInput,)):
                css_class = "form-check-input"
            elif isinstance(widget, (forms.ClearableFileInput,)):
                css_class = "form-control"

            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {css_class}".strip()


class EmailAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"placeholder": "voce@email.com"}))
    password = forms.CharField(label="Senha", strip=False, widget=forms.PasswordInput(attrs={"placeholder": "Sua senha"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


class PatientRegistrationForm(BootstrapFormMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = [
            "full_name",
            "email",
            "cpf",
            "birth_date",
            "phone_primary",
            "cep",
            "street",
            "number",
            "neighborhood",
            "city",
            "state",
            "complement",
        ]
        widgets = {"birth_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PATIENT
        user.approval_status = User.ApprovalStatus.APPROVED
        user.consent_accepted_at = timezone.now()
        user.username = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ClinicRegistrationForm(BootstrapFormMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = [
            "trade_name",
            "company_name",
            "email",
            "cnpj",
            "phone_primary",
            "technical_manager",
            "crm",
            "city",
            "state",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CLINIC
        user.full_name = self.cleaned_data["trade_name"]
        user.approval_status = User.ApprovalStatus.PENDING
        user.is_active = True
        user.username = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ExamForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Exam
        fields = ["title", "exam_type", "performed_at", "file", "notes"]
        widgets = {"performed_at": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_file(self):
        file = self.cleaned_data["file"]
        allowed_extensions = {".jpg", ".jpeg", ".png", ".pdf"}
        extension = file.name[file.name.rfind(".") :].lower()
        if extension not in allowed_extensions:
            raise ValidationError("Envie apenas arquivos JPG, PNG ou PDF.")
        if file.size > 10 * 1024 * 1024:
            raise ValidationError("O arquivo não pode ultrapassar 10 MB.")
        return file


class CycleRecordForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CycleRecord
        fields = ["start_date", "end_date", "symptoms", "notes"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise ValidationError("A data final não pode ser anterior à data inicial.")
        return cleaned_data


class MedicalHistoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MedicalHistory
        fields = ["info_type", "description", "record_date", "observation"]
        widgets = {"record_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


class AccessRequestForm(BootstrapFormMixin, forms.Form):
    patient_cpf = forms.CharField(label="CPF da paciente", max_length=14)
    request_note = forms.CharField(label="Observação", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()


class AppointmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["clinic", "specialist", "scheduled_for"]
        widgets = {"scheduled_for": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["clinic"].queryset = User.objects.filter(
            role=User.Role.CLINIC,
            approval_status=User.ApprovalStatus.APPROVED,
        )
        self.apply_bootstrap()

    def clean_scheduled_for(self):
        scheduled_for = self.cleaned_data["scheduled_for"]
        if scheduled_for <= timezone.now():
            raise ValidationError("Escolha uma data futura para o agendamento.")
        return scheduled_for


class SecureMessageForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SecureMessage
        fields = ["recipient", "body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Escreva sua mensagem..."})}

    def __init__(self, *args, **kwargs):
        allowed_recipients = kwargs.pop("allowed_recipients", User.objects.none())
        super().__init__(*args, **kwargs)
        self.fields["recipient"].queryset = allowed_recipients
        self.apply_bootstrap()


class FAQForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FAQ
        fields = ["question", "answer", "is_active"]
        widgets = {"answer": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()
