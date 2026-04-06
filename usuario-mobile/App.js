import AsyncStorage from "@react-native-async-storage/async-storage";
import * as DocumentPicker from "expo-document-picker";
import { StatusBar } from "expo-status-bar";
import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

const STORAGE_KEYS = {
  apiUrl: "ciclo_api_url",
  token: "ciclo_token",
  user: "ciclo_user",
};

const NAV_ITEMS = [
  { key: "home", label: "Inicio" },
  { key: "exams", label: "Exames" },
  { key: "cycles", label: "Ciclos" },
  { key: "access", label: "Acessos" },
  { key: "appointments", label: "Consultas" },
  { key: "notifications", label: "Alertas" },
  { key: "faq", label: "Ajuda" },
];

function normalizeUrl(url) {
  return url.trim().replace(/\/+$/, "");
}

async function apiRequest(apiUrl, path, { method = "GET", token, body, isFormData = false } = {}) {
  const headers = { Accept: "application/json" };
  if (token) headers.Authorization = `Token ${token}`;
  if (!isFormData) headers["Content-Type"] = "application/json";

  const response = await fetch(`${normalizeUrl(apiUrl)}${path}`, {
    method,
    headers,
    body: isFormData ? body : body ? JSON.stringify(body) : undefined,
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "string" ? payload : payload.detail || JSON.stringify(payload);
    throw new Error(detail || "Falha na requisicao.");
  }
  return payload;
}

function getTimezoneOffsetLabel() {
  const offsetMinutes = -new Date().getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absoluteMinutes = Math.abs(offsetMinutes);
  const hours = String(Math.floor(absoluteMinutes / 60)).padStart(2, "0");
  const minutes = String(absoluteMinutes % 60).padStart(2, "0");
  return `${sign}${hours}:${minutes}`;
}

function buildScheduledFor(datePart, timePart) {
  const normalizedDate = datePart.trim();
  const normalizedTime = timePart.trim();

  if (!/^\d{4}-\d{2}-\d{2}$/.test(normalizedDate)) {
    throw new Error("Use a data no formato AAAA-MM-DD.");
  }

  if (!/^\d{2}:\d{2}$/.test(normalizedTime)) {
    throw new Error("Use a hora no formato HH:MM.");
  }

  return `${normalizedDate}T${normalizedTime}:00${getTimezoneOffsetLabel()}`;
}

function formatScheduledFor(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!match) return value || "-";
  const [, year, month, day, hours, minutes] = match;
  return `${day}/${month}/${year} as ${hours}:${minutes}`;
}

function formatDate(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return value || "-";
  const [, year, month, day] = match;
  return `${day}/${month}/${year}`;
}

function formatDateTime(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!match) return value || "-";
  const [, year, month, day, hours, minutes] = match;
  return `${day}/${month}/${year} as ${hours}:${minutes}`;
}

function getAccessTone(status) {
  if (status === "approved") return "success";
  if (status === "pending") return "warning";
  if (status === "rejected") return "danger";
  return "neutral";
}

function getNotificationTone(item) {
  if (item.is_critical) return "danger";
  if (item.type === "appointment") return "info";
  if (item.type === "exam") return "success";
  if (item.type === "cycle") return "warning";
  return "neutral";
}

function SectionCard({ title, subtitle, children, right }) {
  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View style={{ flex: 1 }}>
          <Text style={styles.cardTitle}>{title}</Text>
          {subtitle ? <Text style={styles.cardSubtitle}>{subtitle}</Text> : null}
        </View>
        {right}
      </View>
      {children}
    </View>
  );
}

function SmallButton({ title, variant = "primary", onPress }) {
  return (
    <Pressable onPress={onPress} style={[styles.smallButton, variant === "secondary" && styles.secondaryButton, variant === "danger" && styles.dangerButton]}>
      <Text style={[styles.smallButtonText, variant !== "primary" && styles.secondaryButtonText]}>{title}</Text>
    </Pressable>
  );
}

function Metric({ label, value }) {
  return (
    <View style={styles.metricBox}>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

function TonePill({ label, tone = "neutral" }) {
  return (
    <View style={[styles.tonePill, tone === "success" && styles.tonePillSuccess, tone === "warning" && styles.tonePillWarning, tone === "danger" && styles.tonePillDanger, tone === "info" && styles.tonePillInfo]}>
      <Text style={[styles.tonePillText, tone === "success" && styles.tonePillTextSuccess, tone === "warning" && styles.tonePillTextWarning, tone === "danger" && styles.tonePillTextDanger, tone === "info" && styles.tonePillTextInfo]}>
        {label}
      </Text>
    </View>
  );
}

function LabeledInput({ label, value, onChangeText, ...props }) {
  return (
    <View style={styles.inputGroup}>
      <Text style={styles.label}>{label}</Text>
      <TextInput value={value} onChangeText={onChangeText} style={styles.input} placeholderTextColor="#7B8AA6" {...props} />
    </View>
  );
}

function AuthScreen({ apiUrl, setApiUrl, onLoginSuccess }) {
  const [mode, setMode] = useState("login");
  const [submitting, setSubmitting] = useState(false);
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [registerForm, setRegisterForm] = useState({
    full_name: "",
    email: "",
    password: "",
    cpf: "",
    phone_primary: "",
    city: "",
    state: "",
  });

  const submitLogin = async () => {
    try {
      setSubmitting(true);
      const data = await apiRequest(apiUrl, "/api/auth/token/", { method: "POST", body: loginForm });
      await onLoginSuccess(data.token, data.user);
    } catch (error) {
      Alert.alert("Falha no login", error.message);
    } finally {
      setSubmitting(false);
    }
  };

  const submitRegister = async () => {
    try {
      setSubmitting(true);
      await apiRequest(apiUrl, "/api/auth/register/patient/", { method: "POST", body: registerForm });
      const data = await apiRequest(apiUrl, "/api/auth/token/", {
        method: "POST",
        body: { email: registerForm.email, password: registerForm.password },
      });
      await onLoginSuccess(data.token, data.user);
    } catch (error) {
      Alert.alert("Falha no cadastro", error.message);
    } finally {
      setSubmitting(false);
    }
  };

  const disabled = !apiUrl || submitting;

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.authContainer}>
        <Text style={styles.eyebrow}>Aplicativo mobile da usuaria</Text>
        <Text style={styles.heroTitle}>Ciclo & Saude</Text>
        <Text style={styles.heroText}>
          App nativo para a paciente acompanhar exames, ciclo menstrual, consentimentos, consultas e notificacoes.
        </Text>

        <SectionCard title="Configuracao da API" subtitle="Use o IP da maquina Django, por exemplo http://192.168.0.15:8000">
          <LabeledInput label="URL do backend" value={apiUrl} onChangeText={setApiUrl} autoCapitalize="none" placeholder="http://192.168.0.15:8000" />
        </SectionCard>

        <View style={styles.modeRow}>
          <Pressable onPress={() => setMode("login")} style={[styles.modeButton, mode === "login" && styles.modeButtonActive]}>
            <Text style={[styles.modeButtonText, mode === "login" && styles.modeButtonTextActive]}>Entrar</Text>
          </Pressable>
          <Pressable onPress={() => setMode("register")} style={[styles.modeButton, mode === "register" && styles.modeButtonActive]}>
            <Text style={[styles.modeButtonText, mode === "register" && styles.modeButtonTextActive]}>Criar conta</Text>
          </Pressable>
        </View>

        {mode === "login" ? (
          <SectionCard title="Entrar">
            <LabeledInput label="E-mail" value={loginForm.email} onChangeText={(value) => setLoginForm((current) => ({ ...current, email: value }))} autoCapitalize="none" keyboardType="email-address" />
            <LabeledInput label="Senha" value={loginForm.password} onChangeText={(value) => setLoginForm((current) => ({ ...current, password: value }))} secureTextEntry />
            <Pressable disabled={disabled} onPress={submitLogin} style={[styles.primaryAction, disabled && styles.disabledAction]}>
              {submitting ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryActionText}>Entrar no app</Text>}
            </Pressable>
          </SectionCard>
        ) : (
          <SectionCard title="Criar conta">
            <LabeledInput label="Nome completo" value={registerForm.full_name} onChangeText={(value) => setRegisterForm((current) => ({ ...current, full_name: value }))} />
            <LabeledInput label="E-mail" value={registerForm.email} onChangeText={(value) => setRegisterForm((current) => ({ ...current, email: value }))} autoCapitalize="none" keyboardType="email-address" />
            <LabeledInput label="Senha" value={registerForm.password} onChangeText={(value) => setRegisterForm((current) => ({ ...current, password: value }))} secureTextEntry />
            <LabeledInput label="CPF" value={registerForm.cpf} onChangeText={(value) => setRegisterForm((current) => ({ ...current, cpf: value }))} />
            <LabeledInput label="Telefone" value={registerForm.phone_primary} onChangeText={(value) => setRegisterForm((current) => ({ ...current, phone_primary: value }))} />
            <LabeledInput label="Cidade" value={registerForm.city} onChangeText={(value) => setRegisterForm((current) => ({ ...current, city: value }))} />
            <LabeledInput label="Estado" value={registerForm.state} onChangeText={(value) => setRegisterForm((current) => ({ ...current, state: value }))} maxLength={2} autoCapitalize="characters" />
            <Pressable disabled={disabled} onPress={submitRegister} style={[styles.primaryAction, disabled && styles.disabledAction]}>
              {submitting ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryActionText}>Cadastrar e entrar</Text>}
            </Pressable>
          </SectionCard>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function DashboardScreen({ data, refresh }) {
  return (
    <ScrollView refreshControl={<RefreshControl refreshing={false} onRefresh={refresh} />} contentContainerStyle={styles.screenContent}>
      <SectionCard title="Visao geral" subtitle="Resumo dos dados da paciente">
        <View style={styles.metricsGrid}>
          <Metric label="Exames ativos" value={data?.exam_count ?? 0} />
          <Metric label="Clinicas autorizadas" value={data?.clinic_links ?? 0} />
          <Metric label="Historicos" value={data?.medical_history_count ?? 0} />
        </View>
      </SectionCard>
      <SectionCard title="Proximo ciclo estimado">
        <Text style={styles.bodyText}>{data?.next_cycle_date ? data.next_cycle_date : "Cadastre dois ciclos para gerar a previsao."}</Text>
      </SectionCard>
      <SectionCard title="Solicitacoes pendentes">
        {data?.pending_requests?.length ? data.pending_requests.map((item) => (
          <View key={item.id} style={styles.listItem}>
            <Text style={styles.listTitle}>{item.clinic.full_name}</Text>
            <Text style={styles.listSubtitle}>Acesso aguardando decisao</Text>
          </View>
        )) : <Text style={styles.bodyText}>Nenhuma solicitacao pendente.</Text>}
      </SectionCard>
    </ScrollView>
  );
}

function ExamsScreen({ apiUrl, token }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [form, setForm] = useState({ title: "", exam_type: "", performed_at: "", notes: "" });

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiRequest(apiUrl, "/api/patient/exams/", { token });
      setItems(data);
    } catch (error) {
      Alert.alert("Falha ao carregar exames", error.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, token]);

  useEffect(() => {
    load();
  }, [load]);

  const pickFile = async () => {
    const result = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true, multiple: false });
    if (!result.canceled && result.assets?.length) setSelectedFile(result.assets[0]);
  };

  const submit = async () => {
    if (!selectedFile) {
      Alert.alert("Arquivo obrigatorio", "Selecione um exame para enviar.");
      return;
    }
    try {
      setUploading(true);
      const body = new FormData();
      body.append("title", form.title);
      body.append("exam_type", form.exam_type);
      body.append("performed_at", form.performed_at);
      body.append("notes", form.notes);
      body.append("file", {
        uri: selectedFile.uri,
        name: selectedFile.name || "exame.pdf",
        type: selectedFile.mimeType || "application/octet-stream",
      });
      await apiRequest(apiUrl, "/api/patient/exams/", { method: "POST", token, body, isFormData: true });
      setForm({ title: "", exam_type: "", performed_at: "", notes: "" });
      setSelectedFile(null);
      await load();
      Alert.alert("Sucesso", "Exame enviado com sucesso.");
    } catch (error) {
      Alert.alert("Falha no upload", error.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <ScrollView refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.screenContent}>
      <SectionCard title="Enviar novo exame" subtitle="Organize seus arquivos de forma clara, com data, tipo e observacoes de apoio.">
        <Text style={styles.sectionStep}>1. Escolha o arquivo</Text>
        <Pressable onPress={pickFile} style={[styles.uploadCard, selectedFile && styles.uploadCardSelected]}>
          <Text style={styles.uploadIcon}>+</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.uploadTitle}>{selectedFile ? selectedFile.name : "Selecionar exame"}</Text>
            <Text style={styles.uploadSubtitle}>
              {selectedFile
                ? `${selectedFile.mimeType || "Arquivo pronto para envio"}${selectedFile.size ? ` • ${Math.round(selectedFile.size / 1024)} KB` : ""}`
                : "Aceita JPG, PNG ou PDF com ate 10 MB"}
            </Text>
          </View>
        </Pressable>

        <Text style={styles.sectionStep}>2. Complete os dados</Text>
        <LabeledInput label="Titulo" value={form.title} onChangeText={(value) => setForm((current) => ({ ...current, title: value }))} />
        <LabeledInput label="Tipo de exame" value={form.exam_type} onChangeText={(value) => setForm((current) => ({ ...current, exam_type: value }))} />
        <View style={styles.rowGap}>
          {["Ultrassom", "Papanicolau", "Mamografia"].map((preset) => (
            <SmallButton
              key={preset}
              title={preset}
              variant={form.exam_type === preset ? "primary" : "secondary"}
              onPress={() => setForm((current) => ({ ...current, exam_type: preset }))}
            />
          ))}
        </View>
        <LabeledInput label="Data de realizacao" value={form.performed_at} onChangeText={(value) => setForm((current) => ({ ...current, performed_at: value }))} placeholder="2026-04-10" autoCapitalize="none" />
        <LabeledInput label="Observacoes" value={form.notes} onChangeText={(value) => setForm((current) => ({ ...current, notes: value }))} multiline />
        <Pressable onPress={submit} style={[styles.primaryAction, uploading && styles.disabledAction]}>
          {uploading ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryActionText}>Enviar exame</Text>}
        </Pressable>
      </SectionCard>
      <SectionCard title="Seus exames" subtitle="Consulte os registros mais recentes do seu historico clinico.">
        {items.map((item) => (
          <View key={item.id} style={styles.examCard}>
            <View style={styles.inlineHeader}>
              <Text style={styles.listTitle}>{item.title}</Text>
              <TonePill label={item.exam_type || "Exame"} tone="info" />
            </View>
            <Text style={styles.listSubtitle}>Realizado em {formatDate(item.performed_at)}</Text>
            {item.notes ? <Text style={styles.bodyText}>{item.notes}</Text> : null}
            <View style={styles.rowGap}>
              <TonePill label="Arquivo enviado" tone={item.file_url ? "success" : "neutral"} />
              <TonePill label={`Upload ${formatDateTime(item.uploaded_at)}`} tone="neutral" />
            </View>
          </View>
        ))}
        {!items.length && !loading ? <Text style={styles.bodyText}>Nenhum exame cadastrado ainda.</Text> : null}
      </SectionCard>
    </ScrollView>
  );
}

function CyclesScreen({ apiUrl, token }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ start_date: "", end_date: "", symptoms: "", notes: "" });

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiRequest(apiUrl, "/api/patient/cycles/", { token });
      setItems(data);
    } catch (error) {
      Alert.alert("Falha ao carregar ciclos", error.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, token]);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async () => {
    try {
      await apiRequest(apiUrl, "/api/patient/cycles/", { method: "POST", token, body: form });
      setForm({ start_date: "", end_date: "", symptoms: "", notes: "" });
      await load();
      Alert.alert("Sucesso", "Ciclo registrado.");
    } catch (error) {
      Alert.alert("Falha ao registrar ciclo", error.message);
    }
  };

  return (
    <ScrollView refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.screenContent}>
      <SectionCard title="Registrar ciclo">
        <LabeledInput label="Inicio (AAAA-MM-DD)" value={form.start_date} onChangeText={(value) => setForm((current) => ({ ...current, start_date: value }))} />
        <LabeledInput label="Fim (AAAA-MM-DD)" value={form.end_date} onChangeText={(value) => setForm((current) => ({ ...current, end_date: value }))} />
        <LabeledInput label="Sintomas" value={form.symptoms} onChangeText={(value) => setForm((current) => ({ ...current, symptoms: value }))} />
        <LabeledInput label="Observacoes" value={form.notes} onChangeText={(value) => setForm((current) => ({ ...current, notes: value }))} multiline />
        <Pressable onPress={submit} style={styles.primaryAction}>
          <Text style={styles.primaryActionText}>Salvar ciclo</Text>
        </Pressable>
      </SectionCard>
      <SectionCard title="Historico">
        {items.map((item) => (
          <View key={item.id} style={styles.listItem}>
            <Text style={styles.listTitle}>{item.start_date} ate {item.end_date}</Text>
            <Text style={styles.listSubtitle}>{item.symptoms || "Sem sintomas informados"}</Text>
          </View>
        ))}
        {!items.length && !loading ? <Text style={styles.bodyText}>Nenhum ciclo cadastrado.</Text> : null}
      </SectionCard>
    </ScrollView>
  );
}

function AccessScreen({ apiUrl, token }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiRequest(apiUrl, "/api/patient/access-requests/", { token });
      setItems(data);
    } catch (error) {
      Alert.alert("Falha ao carregar acessos", error.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, token]);

  useEffect(() => {
    load();
  }, [load]);

  const decide = async (id, action) => {
    try {
      await apiRequest(apiUrl, `/api/patient/access-requests/${id}/decision/`, { method: "POST", token, body: { action } });
      await load();
    } catch (error) {
      Alert.alert("Falha ao atualizar solicitacao", error.message);
    }
  };

  return (
    <ScrollView refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.screenContent}>
      <SectionCard title="Controle de acessos" subtitle="Acompanhe quem pediu acesso aos seus exames e decida com tranquilidade.">
        <View style={styles.metricsGrid}>
          <Metric label="Pendentes" value={items.filter((item) => item.status === "pending").length} />
          <Metric label="Aprovadas" value={items.filter((item) => item.status === "approved").length} />
          <Metric label="Encerradas" value={items.filter((item) => item.status !== "pending" && item.status !== "approved").length} />
        </View>
      </SectionCard>
      <SectionCard title="Solicitacoes recebidas">
        {items.map((item) => (
          <View key={item.id} style={styles.accessCard}>
            <View style={styles.inlineHeader}>
              <Text style={styles.listTitle}>{item.clinic.full_name}</Text>
              <TonePill label={item.status_label} tone={getAccessTone(item.status)} />
            </View>
            <Text style={styles.listSubtitle}>Solicitado em {formatDateTime(item.requested_at)}</Text>
            {item.request_note ? <Text style={styles.bodyText}>{item.request_note}</Text> : <Text style={styles.bodyText}>Sem observacoes adicionais da clinica.</Text>}
            <View style={styles.rowGap}>
              {item.status === "pending" ? (
                <>
                  <SmallButton title="Aprovar" onPress={() => decide(item.id, "approve")} />
                  <SmallButton title="Recusar" variant="danger" onPress={() => decide(item.id, "reject")} />
                </>
              ) : item.status === "approved" ? (
                <SmallButton title="Revogar" variant="danger" onPress={() => decide(item.id, "revoke")} />
              ) : null}
            </View>
          </View>
        ))}
        {!items.length && !loading ? <Text style={styles.bodyText}>Nenhuma solicitacao recebida.</Text> : null}
      </SectionCard>
    </ScrollView>
  );
}

function AppointmentsScreen({ apiUrl, token }) {
  const [items, setItems] = useState([]);
  const [clinics, setClinics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ clinicId: "", specialist: "", appointmentDate: "", appointmentTime: "" });

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [appointments, clinicOptions] = await Promise.all([
        apiRequest(apiUrl, "/api/patient/appointments/", { token }),
        apiRequest(apiUrl, "/api/clinics/"),
      ]);
      setItems(appointments);
      setClinics(clinicOptions);
    } catch (error) {
      Alert.alert("Falha ao carregar consultas", error.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, token]);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async () => {
    try {
      if (!form.clinicId) {
        Alert.alert("Clinica obrigatoria", "Escolha a clinica antes de continuar.");
        return;
      }

      if (!form.specialist.trim()) {
        Alert.alert("Especialista obrigatorio", "Informe a especialidade ou profissional da consulta.");
        return;
      }

      const scheduledFor = buildScheduledFor(form.appointmentDate, form.appointmentTime);
      await apiRequest(apiUrl, "/api/patient/appointments/", {
        method: "POST",
        token,
        body: {
          clinic_id: Number(form.clinicId),
          specialist: form.specialist.trim(),
          scheduled_for: scheduledFor,
        },
      });
      setForm({ clinicId: "", specialist: "", appointmentDate: "", appointmentTime: "" });
      await load();
      Alert.alert("Sucesso", "Consulta agendada.");
    } catch (error) {
      Alert.alert("Falha ao agendar consulta", error.message);
    }
  };

  const selectedClinic = clinics.find((clinic) => String(clinic.id) === String(form.clinicId));
  let appointmentPreview = "Preencha a data e a hora para ver a consulta pronta.";
  if (form.appointmentDate && form.appointmentTime) {
    try {
      appointmentPreview = formatScheduledFor(buildScheduledFor(form.appointmentDate, form.appointmentTime));
    } catch (_error) {
      appointmentPreview = "Use data no formato AAAA-MM-DD e hora no formato HH:MM.";
    }
  }

  return (
    <ScrollView refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.screenContent}>
      <SectionCard title="Agendar consulta" subtitle="Monte o horario em campos separados e o app envia o formato tecnico automaticamente.">
        <Text style={styles.sectionStep}>1. Escolha a clinica</Text>
        <View style={styles.choiceGrid}>
          {clinics.map((clinic) => {
            const isSelected = String(clinic.id) === String(form.clinicId);
            return (
              <Pressable
                key={clinic.id}
                onPress={() => setForm((current) => ({ ...current, clinicId: String(clinic.id) }))}
                style={[styles.choiceCard, isSelected && styles.choiceCardActive]}
              >
                <Text style={[styles.choiceTitle, isSelected && styles.choiceTitleActive]}>{clinic.full_name}</Text>
                <Text style={[styles.choiceSubtitle, isSelected && styles.choiceSubtitleActive]}>{clinic.email}</Text>
                <Text style={[styles.choiceBadge, isSelected && styles.choiceBadgeActive]}>ID #{clinic.id}</Text>
              </Pressable>
            );
          })}
        </View>
        {!clinics.length && !loading ? <Text style={styles.bodyText}>Nenhuma clinica disponivel para agendamento.</Text> : null}

        <Text style={styles.sectionStep}>2. Informe os detalhes</Text>
        <LabeledInput
          label="Especialista"
          value={form.specialist}
          onChangeText={(value) => setForm((current) => ({ ...current, specialist: value }))}
          placeholder="Ex.: Ginecologista"
        />
        <View style={styles.dateTimeRow}>
          <View style={styles.dateTimeColumn}>
            <LabeledInput
              label="Data"
              value={form.appointmentDate}
              onChangeText={(value) => setForm((current) => ({ ...current, appointmentDate: value }))}
              placeholder="2026-04-10"
              autoCapitalize="none"
            />
          </View>
          <View style={styles.dateTimeColumn}>
            <LabeledInput
              label="Hora"
              value={form.appointmentTime}
              onChangeText={(value) => setForm((current) => ({ ...current, appointmentTime: value }))}
              placeholder="14:30"
              autoCapitalize="none"
            />
          </View>
        </View>
        <View style={styles.rowGap}>
          {["09:00", "14:00", "18:30"].map((timeSlot) => (
            <SmallButton
              key={timeSlot}
              title={timeSlot}
              variant={form.appointmentTime === timeSlot ? "primary" : "secondary"}
              onPress={() => setForm((current) => ({ ...current, appointmentTime: timeSlot }))}
            />
          ))}
        </View>
        <View style={styles.previewCard}>
          <Text style={styles.previewEyebrow}>Resumo do agendamento</Text>
          <Text style={styles.previewHeadline}>{selectedClinic ? selectedClinic.full_name : "Selecione uma clinica"}</Text>
          <Text style={styles.previewText}>{appointmentPreview}</Text>
          <Text style={styles.previewCaption}>Formato visual amigavel; a API recebe a data completa com fuso automaticamente.</Text>
        </View>
        <Pressable onPress={submit} style={styles.primaryAction}>
          <Text style={styles.primaryActionText}>Agendar</Text>
        </Pressable>
      </SectionCard>
      <SectionCard title="Consultas agendadas" subtitle="Acompanhe os compromissos mais recentes da sua agenda.">
        {items.map((item) => (
          <View key={item.id} style={styles.appointmentCard}>
            <Text style={styles.appointmentWhen}>{formatScheduledFor(item.scheduled_for)}</Text>
            <Text style={styles.listTitle}>{item.clinic.full_name}</Text>
            <Text style={styles.listSubtitle}>{item.specialist}</Text>
          </View>
        ))}
        {!items.length && !loading ? <Text style={styles.bodyText}>Nenhuma consulta agendada.</Text> : null}
      </SectionCard>
    </ScrollView>
  );
}

function NotificationsScreen({ apiUrl, token, onOpenFaq }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiRequest(apiUrl, "/api/patient/notifications/", { token });
      setItems(data);
    } catch (error) {
      Alert.alert("Falha ao carregar notificacoes", error.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, token]);

  useEffect(() => {
    load();
  }, [load]);

  const markAllRead = async () => {
    try {
      await apiRequest(apiUrl, "/api/patient/notifications/mark-all-read/", { method: "POST", token });
      await load();
    } catch (error) {
      Alert.alert("Falha ao marcar como lidas", error.message);
    }
  };

  return (
    <ScrollView refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.screenContent}>
      <SectionCard title="Central de alertas" subtitle="Veja mensagens importantes sobre exames, ciclos, consultas e seguranca." right={<SmallButton title="Marcar tudo" variant="secondary" onPress={markAllRead} />}>
        <View style={styles.metricsGrid}>
          <Metric label="Total" value={items.length} />
          <Metric label="Criticas" value={items.filter((item) => item.is_critical).length} />
          <Metric label="Nao lidas" value={items.filter((item) => !item.read_at).length} />
        </View>
        <View style={styles.helpPrompt}>
          <Text style={styles.helpPromptText}>Se bater alguma duvida, voce pode abrir a area de Ajuda e consultar as perguntas frequentes do app.</Text>
          <SmallButton title="Abrir FAQ" variant="secondary" onPress={onOpenFaq} />
        </View>
      </SectionCard>
      <SectionCard title="Notificacoes">
        {items.map((item) => (
          <View key={item.id} style={[styles.notificationCard, item.is_critical && styles.notificationCardCritical]}>
            <View style={styles.inlineHeader}>
              <View style={styles.rowGap}>
                <TonePill label={item.type_label} tone={getNotificationTone(item)} />
                {item.is_critical ? <TonePill label="Critica" tone="danger" /> : null}
                {!item.read_at ? <TonePill label="Nova" tone="warning" /> : null}
              </View>
            </View>
            <Text style={styles.notificationMessage}>{item.message}</Text>
            <Text style={styles.notificationMeta}>{formatDateTime(item.created_at)}</Text>
          </View>
        ))}
        {!items.length && !loading ? <Text style={styles.bodyText}>Nenhuma notificacao disponivel.</Text> : null}
      </SectionCard>
    </ScrollView>
  );
}

function FAQScreen({ apiUrl, token }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiRequest(apiUrl, "/api/faqs/", { token });
      setItems(data);
    } catch (error) {
      Alert.alert("Falha ao carregar FAQ", error.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, token]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <ScrollView refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.screenContent}>
      <SectionCard title="Ajuda e FAQ" subtitle="Respostas rapidas para as duvidas mais comuns sobre o uso do aplicativo e da plataforma.">
        <Text style={styles.bodyText}>Se precisar relembrar como o sistema funciona, acompanhe esta area. O conteudo e gerenciado pelo administrador e atualizado sempre que necessario.</Text>
      </SectionCard>
      <SectionCard title="Perguntas frequentes">
        {items.map((item) => (
          <View key={item.id} style={styles.faqCard}>
            <Text style={styles.faqQuestion}>{item.question}</Text>
            <Text style={styles.faqAnswer}>{item.answer}</Text>
          </View>
        ))}
        {!items.length && !loading ? <Text style={styles.bodyText}>Nenhuma pergunta frequente publicada no momento.</Text> : null}
      </SectionCard>
    </ScrollView>
  );
}

export default function App() {
  const [booting, setBooting] = useState(true);
  const [apiUrl, setApiUrl] = useState("");
  const [token, setToken] = useState("");
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState("home");
  const [dashboard, setDashboard] = useState(null);
  const [refreshingDashboard, setRefreshingDashboard] = useState(false);
  const [settingsVisible, setSettingsVisible] = useState(false);
  const [draftApiUrl, setDraftApiUrl] = useState("");

  useEffect(() => {
    (async () => {
      const [savedUrl, savedToken, savedUser] = await Promise.all([
        AsyncStorage.getItem(STORAGE_KEYS.apiUrl),
        AsyncStorage.getItem(STORAGE_KEYS.token),
        AsyncStorage.getItem(STORAGE_KEYS.user),
      ]);
      if (savedUrl) {
        setApiUrl(savedUrl);
        setDraftApiUrl(savedUrl);
      }
      if (savedToken) setToken(savedToken);
      if (savedUser) setUser(JSON.parse(savedUser));
      setBooting(false);
    })();
  }, []);

  const persistSession = async (newToken, newUser) => {
    setToken(newToken);
    setUser(newUser);
    await AsyncStorage.multiSet([
      [STORAGE_KEYS.token, newToken],
      [STORAGE_KEYS.user, JSON.stringify(newUser)],
      [STORAGE_KEYS.apiUrl, normalizeUrl(apiUrl)],
    ]);
  };

  const logout = async () => {
    try {
      if (token && apiUrl) await apiRequest(apiUrl, "/api/auth/logout/", { method: "POST", token });
    } catch (_) {
      // no-op
    } finally {
      setToken("");
      setUser(null);
      await AsyncStorage.multiRemove([STORAGE_KEYS.token, STORAGE_KEYS.user]);
    }
  };

  const refreshDashboard = useCallback(async () => {
    if (!token || !apiUrl) return;
    try {
      setRefreshingDashboard(true);
      const data = await apiRequest(apiUrl, "/api/patient/dashboard/", { token });
      setDashboard(data);
    } catch (error) {
      Alert.alert("Falha ao atualizar dashboard", error.message);
    } finally {
      setRefreshingDashboard(false);
    }
  }, [apiUrl, token]);

  useEffect(() => {
    if (token && apiUrl) refreshDashboard();
  }, [token, apiUrl, refreshDashboard]);

  let activeScreen = <NotificationsScreen apiUrl={apiUrl} token={token} onOpenFaq={() => setActiveTab("faq")} />;
  if (activeTab === "home") activeScreen = <DashboardScreen data={dashboard} refresh={refreshDashboard} />;
  if (activeTab === "exams") activeScreen = <ExamsScreen apiUrl={apiUrl} token={token} />;
  if (activeTab === "cycles") activeScreen = <CyclesScreen apiUrl={apiUrl} token={token} />;
  if (activeTab === "access") activeScreen = <AccessScreen apiUrl={apiUrl} token={token} />;
  if (activeTab === "appointments") activeScreen = <AppointmentsScreen apiUrl={apiUrl} token={token} />;
  if (activeTab === "faq") activeScreen = <FAQScreen apiUrl={apiUrl} token={token} />;

  if (booting) {
    return (
      <SafeAreaView style={[styles.safeArea, styles.centered]}>
        <ActivityIndicator size="large" color="#0B5FFF" />
      </SafeAreaView>
    );
  }

  if (!token || !user) {
    return <AuthScreen apiUrl={apiUrl} setApiUrl={setApiUrl} onLoginSuccess={persistSession} />;
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <View style={styles.appHeader}>
        <View>
          <Text style={styles.eyebrow}>Paciente</Text>
          <Text style={styles.appTitle}>Ola, {user.full_name?.split(" ")[0]}</Text>
          <Text style={styles.appSubtitle}>{normalizeUrl(apiUrl)}</Text>
        </View>
        <View style={styles.headerStack}>
          <SmallButton title="API" variant="secondary" onPress={() => setSettingsVisible(true)} />
          <SmallButton title={refreshingDashboard ? "..." : "Sair"} variant="danger" onPress={logout} />
        </View>
      </View>

      {activeScreen}

      <View style={styles.bottomNav}>
        {NAV_ITEMS.map((item) => (
          <Pressable key={item.key} onPress={() => setActiveTab(item.key)} style={[styles.navItem, activeTab === item.key && styles.navItemActive]}>
            <Text style={[styles.navText, activeTab === item.key && styles.navTextActive]}>{item.label}</Text>
          </Pressable>
        ))}
      </View>

      <Modal visible={settingsVisible} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.cardTitle}>Configurar backend</Text>
            <LabeledInput label="URL da API" value={draftApiUrl} onChangeText={setDraftApiUrl} autoCapitalize="none" />
            <View style={styles.rowGap}>
              <SmallButton title="Cancelar" variant="secondary" onPress={() => setSettingsVisible(false)} />
              <SmallButton
                title="Salvar"
                onPress={async () => {
                  const value = normalizeUrl(draftApiUrl);
                  setApiUrl(value);
                  await AsyncStorage.setItem(STORAGE_KEYS.apiUrl, value);
                  setSettingsVisible(false);
                }}
              />
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#F4F7FB",
  },
  centered: {
    alignItems: "center",
    justifyContent: "center",
  },
  authContainer: {
    padding: 20,
    gap: 16,
  },
  eyebrow: {
    color: "#0B5FFF",
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
    fontSize: 12,
  },
  heroTitle: {
    fontSize: 34,
    fontWeight: "800",
    color: "#152238",
  },
  heroText: {
    color: "#5A6B85",
    fontSize: 16,
    lineHeight: 24,
  },
  modeRow: {
    flexDirection: "row",
    backgroundColor: "#EAF1FF",
    borderRadius: 18,
    padding: 6,
  },
  modeButton: {
    flex: 1,
    paddingVertical: 12,
    alignItems: "center",
    borderRadius: 12,
  },
  modeButtonActive: {
    backgroundColor: "#0B5FFF",
  },
  modeButtonText: {
    color: "#0B5FFF",
    fontWeight: "700",
  },
  modeButtonTextActive: {
    color: "#FFFFFF",
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    padding: 18,
    borderWidth: 1,
    borderColor: "#DCE6F4",
    shadowColor: "#17314F",
    shadowOpacity: 0.08,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 2,
    gap: 12,
  },
  cardHeader: {
    flexDirection: "row",
    gap: 12,
    alignItems: "center",
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#152238",
  },
  cardSubtitle: {
    marginTop: 4,
    color: "#72839C",
  },
  inputGroup: {
    gap: 6,
  },
  label: {
    fontSize: 13,
    fontWeight: "700",
    color: "#304258",
  },
  input: {
    backgroundColor: "#F8FAFD",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#D7E2F2",
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: "#152238",
  },
  primaryAction: {
    backgroundColor: "#0B5FFF",
    borderRadius: 18,
    paddingVertical: 14,
    alignItems: "center",
  },
  disabledAction: {
    opacity: 0.6,
  },
  primaryActionText: {
    color: "#FFFFFF",
    fontWeight: "800",
    fontSize: 15,
  },
  screenContent: {
    padding: 16,
    gap: 16,
    paddingBottom: 104,
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  metricBox: {
    flexBasis: "30%",
    minWidth: 92,
    backgroundColor: "#F4F8FF",
    borderRadius: 18,
    padding: 14,
  },
  metricValue: {
    fontSize: 22,
    fontWeight: "800",
    color: "#0B5FFF",
  },
  metricLabel: {
    marginTop: 6,
    color: "#54657D",
    fontSize: 12,
  },
  tonePill: {
    alignSelf: "flex-start",
    backgroundColor: "#EEF3FA",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  tonePillSuccess: {
    backgroundColor: "#E7F7EE",
  },
  tonePillWarning: {
    backgroundColor: "#FFF4DA",
  },
  tonePillDanger: {
    backgroundColor: "#FDEBEC",
  },
  tonePillInfo: {
    backgroundColor: "#EAF1FF",
  },
  tonePillText: {
    color: "#54657D",
    fontSize: 12,
    fontWeight: "800",
  },
  tonePillTextSuccess: {
    color: "#18794E",
  },
  tonePillTextWarning: {
    color: "#9A6700",
  },
  tonePillTextDanger: {
    color: "#B42318",
  },
  tonePillTextInfo: {
    color: "#0B5FFF",
  },
  bodyText: {
    color: "#506178",
    lineHeight: 22,
  },
  inlineHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 12,
  },
  listItem: {
    borderTopWidth: 1,
    borderTopColor: "#E8EEF7",
    paddingTop: 12,
    gap: 6,
  },
  listTitle: {
    fontWeight: "800",
    color: "#152238",
  },
  listSubtitle: {
    color: "#667891",
  },
  sectionStep: {
    fontSize: 13,
    fontWeight: "800",
    color: "#45607F",
    letterSpacing: 0.3,
  },
  smallButton: {
    backgroundColor: "#0B5FFF",
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 14,
  },
  secondaryButton: {
    backgroundColor: "#EAF1FF",
  },
  dangerButton: {
    backgroundColor: "#FDEBEC",
  },
  smallButtonText: {
    color: "#FFFFFF",
    fontWeight: "700",
  },
  secondaryButtonText: {
    color: "#0B5FFF",
  },
  rowGap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  choiceGrid: {
    gap: 10,
  },
  uploadCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    backgroundColor: "#F8FAFD",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#D7E2F2",
    padding: 16,
  },
  uploadCardSelected: {
    backgroundColor: "#F4F8FF",
    borderColor: "#AFCBFF",
  },
  uploadIcon: {
    width: 40,
    height: 40,
    borderRadius: 14,
    backgroundColor: "#EAF1FF",
    color: "#0B5FFF",
    textAlign: "center",
    textAlignVertical: "center",
    fontSize: 24,
    fontWeight: "700",
    overflow: "hidden",
    paddingTop: 2,
  },
  uploadTitle: {
    color: "#152238",
    fontSize: 15,
    fontWeight: "800",
  },
  uploadSubtitle: {
    marginTop: 4,
    color: "#667891",
    lineHeight: 20,
  },
  helpPrompt: {
    marginTop: 4,
    backgroundColor: "#F8FAFD",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#D7E2F2",
    padding: 14,
    gap: 10,
  },
  helpPromptText: {
    color: "#506178",
    lineHeight: 21,
  },
  choiceCard: {
    backgroundColor: "#F8FAFD",
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#D7E2F2",
    padding: 14,
    gap: 6,
  },
  choiceCardActive: {
    backgroundColor: "#0B5FFF",
    borderColor: "#0B5FFF",
  },
  choiceTitle: {
    color: "#152238",
    fontSize: 15,
    fontWeight: "800",
  },
  choiceTitleActive: {
    color: "#FFFFFF",
  },
  choiceSubtitle: {
    color: "#667891",
  },
  choiceSubtitleActive: {
    color: "#D6E4FF",
  },
  choiceBadge: {
    alignSelf: "flex-start",
    backgroundColor: "#EAF1FF",
    color: "#0B5FFF",
    borderRadius: 999,
    overflow: "hidden",
    paddingHorizontal: 10,
    paddingVertical: 6,
    fontSize: 12,
    fontWeight: "700",
  },
  choiceBadgeActive: {
    backgroundColor: "#FFFFFF",
    color: "#0B5FFF",
  },
  dateTimeRow: {
    flexDirection: "row",
    gap: 12,
  },
  dateTimeColumn: {
    flex: 1,
  },
  previewCard: {
    backgroundColor: "#F4F8FF",
    borderRadius: 20,
    padding: 16,
    gap: 6,
    borderWidth: 1,
    borderColor: "#D7E2F2",
  },
  previewEyebrow: {
    color: "#5C74A4",
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0.4,
    textTransform: "uppercase",
  },
  previewHeadline: {
    color: "#152238",
    fontSize: 17,
    fontWeight: "800",
  },
  previewText: {
    color: "#304258",
    fontSize: 15,
    fontWeight: "700",
  },
  previewCaption: {
    color: "#6F82A0",
    lineHeight: 20,
  },
  examCard: {
    borderTopWidth: 1,
    borderTopColor: "#E8EEF7",
    paddingTop: 14,
    gap: 8,
  },
  accessCard: {
    borderTopWidth: 1,
    borderTopColor: "#E8EEF7",
    paddingTop: 14,
    gap: 8,
  },
  appointmentCard: {
    borderTopWidth: 1,
    borderTopColor: "#E8EEF7",
    paddingTop: 14,
    gap: 6,
  },
  appointmentWhen: {
    alignSelf: "flex-start",
    backgroundColor: "#EAF1FF",
    color: "#0B5FFF",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    overflow: "hidden",
    fontWeight: "800",
  },
  notificationCard: {
    borderTopWidth: 1,
    borderTopColor: "#E8EEF7",
    paddingTop: 14,
    gap: 8,
  },
  notificationCardCritical: {
    backgroundColor: "#FFF9F9",
    marginHorizontal: -6,
    paddingHorizontal: 6,
    borderRadius: 14,
  },
  notificationMessage: {
    color: "#152238",
    fontSize: 15,
    fontWeight: "700",
    lineHeight: 22,
  },
  notificationMeta: {
    color: "#72839C",
    fontSize: 12,
    fontWeight: "700",
  },
  faqCard: {
    borderTopWidth: 1,
    borderTopColor: "#E8EEF7",
    paddingTop: 14,
    gap: 8,
  },
  faqQuestion: {
    color: "#152238",
    fontSize: 16,
    fontWeight: "800",
    lineHeight: 22,
  },
  faqAnswer: {
    color: "#54657D",
    lineHeight: 22,
  },
  appHeader: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 10,
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 16,
    alignItems: "center",
  },
  appTitle: {
    fontSize: 26,
    fontWeight: "800",
    color: "#152238",
  },
  appSubtitle: {
    marginTop: 4,
    color: "#72839C",
    maxWidth: 220,
  },
  headerStack: {
    gap: 8,
  },
  bottomNav: {
    position: "absolute",
    bottom: 12,
    left: 16,
    right: 16,
    backgroundColor: "rgba(255,255,255,0.96)",
    borderRadius: 20,
    paddingHorizontal: 8,
    paddingVertical: 8,
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    gap: 6,
    borderWidth: 1,
    borderColor: "#D7E2F2",
  },
  navItem: {
    flexBasis: "23%",
    minWidth: 0,
    paddingVertical: 8,
    paddingHorizontal: 8,
    borderRadius: 12,
    alignItems: "center",
  },
  navItemActive: {
    backgroundColor: "#0B5FFF",
  },
  navText: {
    color: "#5E728D",
    fontWeight: "700",
    fontSize: 11,
  },
  navTextActive: {
    color: "#FFFFFF",
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(9,17,31,0.45)",
    justifyContent: "flex-end",
  },
  modalCard: {
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 18,
    gap: 12,
  },
});
