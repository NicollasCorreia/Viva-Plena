import AsyncStorage from "@react-native-async-storage/async-storage";
import * as DocumentPicker from "expo-document-picker";
import { StatusBar } from "expo-status-bar";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  Keyboard,
  KeyboardAvoidingView,
  Linking,
  Modal,
  Platform,
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
  apiUrl: "viva_plena_api_url",
  token: "viva_plena_token",
  user: "viva_plena_user",
};

const LEGACY_STORAGE_KEYS = {
  apiUrl: "ciclo_api_url",
  token: "ciclo_token",
  user: "ciclo_user",
};

const INSTITUTION_NAME = "CESMAC";

const NAV_ITEMS = [
  { key: "home", label: "Painel", icon: "home" },
  { key: "exams", label: "Exames", icon: "document-text" },
  { key: "cycles", label: "Ciclo", icon: "calendar" },
  { key: "access", label: "Acessos", icon: "key" },
  { key: "messages", label: "Mensagens", icon: "chatbubble-ellipses" },
  { key: "appointments", label: "Consultas", icon: "medkit" },
  { key: "notifications", label: "Avisos", icon: "notifications" },
  { key: "faq", label: "Ajuda", icon: "help-circle" },
];

const FIELD_LABELS = {
  full_name: "Nome completo",
  email: "E-mail",
  password: "Senha",
  cpf: "CPF",
  phone_primary: "Telefone",
  city: "Cidade",
  state: "Estado",
  birth_date: "Data de nascimento",
  cep: "CEP",
  street: "Rua",
  number: "Número",
  neighborhood: "Bairro",
  complement: "Complemento",
  title: "Nome do exame",
  exam_type: "Tipo de exame",
  performed_at: "Data do exame",
  notes: "Observações",
  file: "Arquivo do exame",
  start_date: "Início do ciclo",
  end_date: "Fim do ciclo",
  symptoms: "Sintomas",
  clinic_id: "Profissional",
  professional_id: "Profissional",
  specialist: "Profissional ou especialidade",
  scheduled_for: "Data e horário",
  recipient_id: "Destinatário",
  body: "Mensagem",
  patient_cpf: "CPF da paciente",
  request_note: "Mensagem para a paciente",
  detail: "Detalhes",
};

function normalizeUrl(url) {
  return url.trim().replace(/\/+$/, "");
}

async function getStoredValue(primaryKey, legacyKey) {
  const currentValue = await AsyncStorage.getItem(primaryKey);
  if (currentValue !== null) return currentValue;

  const legacyValue = await AsyncStorage.getItem(legacyKey);
  if (legacyValue !== null) {
    await AsyncStorage.setItem(primaryKey, legacyValue);
    await AsyncStorage.removeItem(legacyKey);
  }

  return legacyValue;
}

function getFieldLabel(fieldName) {
  if (FIELD_LABELS[fieldName]) return FIELD_LABELS[fieldName];
  return String(fieldName || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function normalizeApiError(detail) {
  if (!detail) return "Não foi possível concluir essa ação.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => normalizeApiError(item)).join("\n");
  if (typeof detail === "object") {
    if (detail.detail) return normalizeApiError(detail.detail);
    return Object.entries(detail)
      .map(([fieldName, value]) => `${getFieldLabel(fieldName)}: ${normalizeApiError(value)}`)
      .join("\n");
  }
  return "Não foi possível concluir essa ação.";
}

async function apiRequest(apiUrl, path, { method = "GET", token, body, isFormData = false } = {}) {
  const headers = { Accept: "application/json" };
  if (token) headers.Authorization = `Token ${token}`;
  if (!isFormData) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(`${normalizeUrl(apiUrl)}${path}`, {
      method,
      headers,
      body: isFormData ? body : body ? JSON.stringify(body) : undefined,
    });
  } catch (error) {
    throw new Error(
      "Nao foi possivel alcancar o servidor. Verifique se o backend esta rodando, se o app usa o IP atual da maquina e se o Android pode acessar HTTP local."
    );
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "string" ? payload : normalizeApiError(payload);
    const error = new Error(detail || "Não foi possível concluir essa ação.");
    error.status = response.status;
    throw error;
  }
  return payload;
}

function ensurePatientUser(user) {
  if (user?.role !== "patient") {
    throw new Error("Este aplicativo é destinado à conta da paciente. Se você entrou com outro perfil, use o acesso correspondente.");
  }
  return user;
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

function maskDateInput(value) {
  let digits = String(value || "").replace(/\D/g, "");
  if (digits.length > 8) digits = digits.slice(0, 8);
  if (digits.length >= 5) return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
  if (digits.length >= 3) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return digits;
}

function formatFilterDateForApi(value) {
  const rawValue = String(value || "").trim();
  if (!rawValue) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(rawValue)) return rawValue;

  const match = rawValue.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!match) return "";

  const [, day, month, year] = match;
  return `${year}-${month}-${day}`;
}

function buildExamFilterPath(filters = {}) {
  const params = [];
  const performedFrom = formatFilterDateForApi(filters.performedFrom);
  const performedTo = formatFilterDateForApi(filters.performedTo);

  if (performedFrom) params.push(`performed_from=${encodeURIComponent(performedFrom)}`);
  if (performedTo) params.push(`performed_to=${encodeURIComponent(performedTo)}`);
  if (filters.sort) params.push(`sort=${encodeURIComponent(filters.sort)}`);

  return params.length ? `/api/patient/exams/?${params.join("&")}` : "/api/patient/exams/";
}

function getFileExtension(fileUrl) {
  const cleanUrl = String(fileUrl || "").split("?")[0].split("#")[0];
  const match = cleanUrl.match(/\.([a-z0-9]+)$/i);
  return match ? match[1].toLowerCase() : "";
}

function isPreviewableExamImage(fileUrl) {
  return ["jpg", "jpeg", "png"].includes(getFileExtension(fileUrl));
}

function getProfessional(item) {
  return item?.professional || item?.clinic || null;
}

function formatProfessionalDetails(professional) {
  if (!professional) return INSTITUTION_NAME;
  const details = [];
  if (professional.specialty) details.push(professional.specialty);
  if (professional.crm) details.push(professional.crm);
  details.push(professional.institution_name || INSTITUTION_NAME);
  return details.join(" • ");
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

function getAppointmentTone(status) {
  if (status === "scheduled") return "info";
  if (status === "completed") return "success";
  if (status === "cancelled") return "danger";
  return "neutral";
}

function isSecureMessageNotification(item) {
  return /mensagem segura/i.test(String(item?.message || ""));
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

function SmallButton({ title, variant = "primary", onPress, disabled = false }) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={[
        styles.smallButton,
        variant === "secondary" && styles.secondaryButton,
        variant === "danger" && styles.dangerButton,
        disabled && styles.disabledAction,
      ]}
    >
      <Text
        style={[
          styles.smallButtonText,
          variant === "secondary" && styles.secondaryButtonText,
          variant === "danger" && styles.dangerButtonText,
        ]}
      >
        {title}
      </Text>
    </Pressable>
  );
}

function Metric({ label, value }) {
  return (
    <View style={styles.metricBox}>
      <Text style={styles.metricValue} numberOfLines={1} adjustsFontSizeToFit>{value}</Text>
      <Text style={styles.metricLabel} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8}>{label}</Text>
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

function ScreenScroll({ children, contentContainerStyle, ...props }) {
  return (
    <KeyboardAvoidingView
      style={styles.flexFill}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={Platform.OS === "ios" ? 0 : 20}
    >
      <ScrollView
        contentContainerStyle={contentContainerStyle}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode={Platform.OS === "ios" ? "interactive" : "on-drag"}
        showsVerticalScrollIndicator={false}
        {...props}
      >
        {children}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function ScreenIntro({ eyebrow, title, subtitle, children }) {
  return (
    <View style={styles.screenIntro}>
      {eyebrow ? <Text style={styles.screenIntroEyebrow}>{eyebrow}</Text> : null}
      <Text style={styles.screenIntroTitle}>{title}</Text>
      <Text style={styles.screenIntroText}>{subtitle}</Text>
      {children ? <View style={styles.screenIntroFooter}>{children}</View> : null}
    </View>
  );
}

function EmptyState({ title, description }) {
  return (
    <View style={styles.emptyState}>
      <Text style={styles.emptyStateTitle}>{title}</Text>
      <Text style={styles.emptyStateText}>{description}</Text>
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
      await onLoginSuccess(data.token, ensurePatientUser(data.user));
    } catch (error) {
      Alert.alert("Não foi possível entrar", error.message);
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
      await onLoginSuccess(data.token, ensurePatientUser(data.user));
    } catch (error) {
      Alert.alert("Não foi possível criar a conta", error.message);
    } finally {
      setSubmitting(false);
    }
  };

  const disabled = !apiUrl || submitting;

  return (
    <LinearGradient colors={['#FCA5A5', '#E0F2FE']} style={styles.safeArea}>
      <SafeAreaView style={{flex: 1}}>
        <StatusBar style="dark" />
        <ScreenScroll contentContainerStyle={styles.authContainer}>
        <View style={{ alignItems: "center", marginTop: 40, marginBottom: 40 }}>
           <Ionicons name="flower-outline" size={60} color="#FFFFFF" style={{ marginBottom: 16 }} />
           <Text style={{ color: "#FFFFFF", fontSize: 28, fontWeight: "900", letterSpacing: -0.5 }}>Viva Plena</Text>
           <Text style={{ color: "#9A3838", fontSize: 16, marginTop: 8, opacity: 0.95 }}>Acompanhe seu ciclo e exames com mais clareza.</Text>
        </View>

        <View style={{ backgroundColor: "#FFFFFF", borderTopLeftRadius: 36, borderTopRightRadius: 36, paddingTop: 30, paddingHorizontal: 24, paddingBottom: 40, shadowColor: "#000", shadowOpacity: 0.1, shadowRadius: 20, elevation: 10 }}>
          <View style={styles.modeRow}>
            <Pressable onPress={() => setMode("login")} style={[styles.modeButton, mode === "login" && styles.modeButtonActive]}>
              <Text style={[styles.modeButtonText, mode === "login" && styles.modeButtonTextActive]}>Entrar</Text>
            </Pressable>
            <Pressable onPress={() => setMode("register")} style={[styles.modeButton, mode === "register" && styles.modeButtonActive]}>
              <Text style={[styles.modeButtonText, mode === "register" && styles.modeButtonTextActive]}>Criar conta</Text>
            </Pressable>
          </View>

          <View style={{ marginBottom: 20 }}>
             <LabeledInput label="Endereço do sistema (Servidor)" value={apiUrl} onChangeText={setApiUrl} autoCapitalize="none" placeholder="http://192.168.0.15:8000" />
          </View>

          {mode === "login" ? (
            <View>
            <LabeledInput label="E-mail" value={loginForm.email} onChangeText={(value) => setLoginForm((current) => ({ ...current, email: value }))} autoCapitalize="none" keyboardType="email-address" placeholder="nome@exemplo.com" />
            <LabeledInput label="Senha" value={loginForm.password} onChangeText={(value) => setLoginForm((current) => ({ ...current, password: value }))} secureTextEntry placeholder="Digite sua senha" />
            <Pressable disabled={disabled} onPress={submitLogin} style={[styles.primaryAction, disabled && styles.disabledAction]}>
              {submitting ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryActionText}>Entrar na conta</Text>}
            </Pressable>
            </View>
          ) : (
            <View>
              <LabeledInput label="Nome completo" value={registerForm.full_name} onChangeText={(value) => setRegisterForm((current) => ({ ...current, full_name: value }))} placeholder="Como aparece no seu documento" />
              <LabeledInput label="E-mail" value={registerForm.email} onChangeText={(value) => setRegisterForm((current) => ({ ...current, email: value }))} autoCapitalize="none" keyboardType="email-address" placeholder="nome@exemplo.com" />
              <LabeledInput label="Senha" value={registerForm.password} onChangeText={(value) => setRegisterForm((current) => ({ ...current, password: value }))} secureTextEntry placeholder="Use pelo menos 8 caracteres" />
              <LabeledInput label="CPF" value={registerForm.cpf} onChangeText={(value) => setRegisterForm((current) => ({ ...current, cpf: value }))} placeholder="000.000.000-00" />
              <LabeledInput label="Telefone" value={registerForm.phone_primary} onChangeText={(value) => setRegisterForm((current) => ({ ...current, phone_primary: value }))} placeholder="(82) 99999-0000" />
              <LabeledInput label="Cidade" value={registerForm.city} onChangeText={(value) => setRegisterForm((current) => ({ ...current, city: value }))} placeholder="Sua cidade" />
              <LabeledInput label="Estado" value={registerForm.state} onChangeText={(value) => setRegisterForm((current) => ({ ...current, state: value }))} maxLength={2} autoCapitalize="characters" placeholder="AL" />
              <Pressable disabled={disabled} onPress={submitRegister} style={[styles.primaryAction, disabled && styles.disabledAction]}>
                {submitting ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryActionText}>Criar conta</Text>}
              </Pressable>
            </View>
          )}
        </View>
      </ScreenScroll>
      </SafeAreaView>
    </LinearGradient>
  );
}

function DashboardScreen({ data, refresh }) {
  const pendingCount = data?.pending_requests?.length || 0;
  const nextCycleText = data?.next_cycle_date ? formatDate(data.next_cycle_date) : "Registre ao menos dois ciclos para gerar uma previsão.";

  return (
    <ScreenScroll refreshControl={<RefreshControl refreshing={false} onRefresh={refresh} />} contentContainerStyle={styles.screenContent}>
      <ScreenIntro eyebrow="Seu painel" title="Seu cuidado em um só lugar" subtitle="Revise o que precisa da sua atenção e siga sua rotina com mais tranquilidade.">
        <View style={styles.screenIntroBadgeRow}>
          <TonePill label={`Próximo ciclo: ${data?.next_cycle_date ? formatDate(data.next_cycle_date) : "a calcular"}`} tone="info" />
          <TonePill label={pendingCount ? `${pendingCount} pedido(s) aguardando` : "Sem pendências"} tone={pendingCount ? "warning" : "success"} />
        </View>
      </ScreenIntro>
      <SectionCard title="Visão geral" subtitle="Resumo do que está disponível para você">
        <View style={styles.metricsGrid}>
          <Metric label="Exames" value={data?.exam_count ?? 0} />
          <Metric label="Profissionais" value={data?.professional_links ?? data?.clinic_links ?? 0} />
          <Metric label="Registros" value={data?.medical_history_count ?? 0} />
        </View>
      </SectionCard>
      <SectionCard title="Sua privacidade" subtitle="Seus exames só ficam visíveis para quem você autorizar individualmente.">
        <Text style={styles.bodyText}>
          No fluxo atual do CESMAC, cada pedido de acesso é ligado a uma profissional específica. Você pode aprovar, recusar ou encerrar esse acesso quando quiser.
        </Text>
      </SectionCard>
      <SectionCard title="Próximo ciclo estimado">
        <Text style={styles.bodyText}>{nextCycleText}</Text>
      </SectionCard>
      <SectionCard title="Pedidos aguardando sua resposta">
        {data?.pending_requests?.length ? data.pending_requests.map((item) => (
          <View key={item.id} style={styles.listItem}>
            <Text style={styles.listTitle}>{getProfessional(item)?.full_name || "Profissional CESMAC"}</Text>
            <Text style={styles.listSubtitle}>{formatProfessionalDetails(getProfessional(item))}</Text>
          </View>
        )) : <EmptyState title="Nenhum pedido pendente" description="Quando uma profissional solicitar acesso aos seus exames, esse pedido vai aparecer aqui." />}
      </SectionCard>
    </ScreenScroll>
    /*

                  {previewItem ? `${previewItem.exam_type || "Exame"} â€¢ ${formatDate(previewItem.performed_at)}` : ""}
    */
  );
}

function ExamsScreen({ apiUrl, token }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingExamId, setDeletingExamId] = useState(null);
  const [previewItem, setPreviewItem] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [form, setForm] = useState({ title: "", exam_type: "", performed_at: "", notes: "" });
  const [filters, setFilters] = useState({ performedFrom: "", performedTo: "", sort: "recent_upload" });
  const [filterForm, setFilterForm] = useState({ performedFrom: "", performedTo: "", sort: "recent_upload" });

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiRequest(apiUrl, buildExamFilterPath(filters), { token });
      setItems(data);
    } catch (error) {
      Alert.alert("Não foi possível carregar seus exames", error.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, filters, token]);

  useEffect(() => {
    load();
  }, [load]);

  const pickFile = async () => {
    const result = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true, multiple: false });
    if (!result.canceled && result.assets?.length) setSelectedFile(result.assets[0]);
  };

  const openFileExternally = async (fileUrl) => {
    try {
      await Linking.openURL(fileUrl);
    } catch (_) {
      Alert.alert("Nao foi possivel abrir o exame", "Tente novamente em alguns instantes.");
    }
  };

  const openExam = async (item) => {
    if (!item.file_url) {
      Alert.alert("Arquivo indisponivel", "Este exame nao tem um arquivo disponivel no momento.");
      return;
    }

    if (isPreviewableExamImage(item.file_url)) {
      setPreviewItem(item);
      return;
    }

    await openFileExternally(item.file_url);
  };

  const deleteExam = async (item) => {
    try {
      setDeletingExamId(item.id);
      await apiRequest(apiUrl, `/api/patient/exams/${item.id}/`, { method: "DELETE", token });
      setItems((current) => current.filter((exam) => exam.id !== item.id));
      if (previewItem?.id === item.id) setPreviewItem(null);
      Alert.alert("Exame apagado", "O exame foi removido com sucesso.");
    } catch (error) {
      Alert.alert("Nao foi possivel apagar o exame", error.message);
    } finally {
      setDeletingExamId(null);
    }
  };

  const confirmDeleteExam = (item) => {
    Alert.alert(
      "Apagar exame?",
      "Esse exame sera removido da sua lista e o arquivo deixara de ficar disponivel.",
      [
        { text: "Cancelar", style: "cancel" },
        { text: "Apagar", style: "destructive", onPress: () => deleteExam(item) },
      ],
    );
  };

  const submit = async () => {
    if (!selectedFile) {
      Alert.alert("Selecione um arquivo", "Escolha o exame que você quer enviar.");
      return;
    }
    try {
      setUploading(true);
      
      let d = form.performed_at;
      if (d && d.includes('/')) {
         d = d.split('/').reverse().join('-');
      }

      const body = new FormData();
      body.append("title", form.title);
      body.append("exam_type", form.exam_type);
      body.append("performed_at", d);
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
      Alert.alert("Exame enviado", "Seu exame foi salvo com sucesso.");
    } catch (error) {
      Alert.alert("Não foi possível enviar o exame", error.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <>
      <ScreenScroll refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.screenContent}>
      <ScreenIntro eyebrow="Exames" title="Organize seus arquivos com clareza" subtitle="Salve exames com nome, tipo, data e observações para consultar tudo com mais facilidade." />
      <SectionCard title="Enviar novo exame" subtitle="Guarde seus arquivos com nome, data e observações, se quiser.">
        <Text style={styles.sectionStep}>1. Escolha o arquivo</Text>
        <Pressable onPress={pickFile} style={[styles.uploadCard, selectedFile && styles.uploadCardSelected]}>
          <Text style={styles.uploadIcon}>+</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.uploadTitle}>{selectedFile ? selectedFile.name : "Selecionar exame"}</Text>
            <Text style={styles.uploadSubtitle}>
              {selectedFile
                ? `${selectedFile.mimeType || "Arquivo pronto para envio"}${selectedFile.size ? ` • ${Math.round(selectedFile.size / 1024)} KB` : ""}`
                : "Aceitamos JPG, PNG ou PDF com até 10 MB"}
            </Text>
          </View>
        </Pressable>

        <Text style={styles.sectionStep}>2. Complete os dados</Text>
        <LabeledInput label="Nome do exame" value={form.title} onChangeText={(value) => setForm((current) => ({ ...current, title: value }))} />
        <LabeledInput label="Tipo de exame" value={form.exam_type} onChangeText={(value) => setForm((current) => ({ ...current, exam_type: value }))} placeholder="Ex.: Ultrassom" />
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
        <LabeledInput
          label="Data do exame (DD/MM/AAAA)"
          value={form.performed_at}
          onChangeText={(value) => setForm((current) => ({ ...current, performed_at: maskDateInput(value) }))}
          placeholder="10/04/2026"
          keyboardType="numeric"
          autoCapitalize="none"
        />
        <LabeledInput label="Observações (opcional)" value={form.notes} onChangeText={(value) => setForm((current) => ({ ...current, notes: value }))} multiline />
        <Pressable onPress={submit} style={[styles.primaryAction, uploading && styles.disabledAction]}>
          {uploading ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryActionText}>Enviar exame</Text>}
        </Pressable>
      </SectionCard>
      <SectionCard title="Filtrar exames" subtitle="Encontre por intervalo de datas e priorize os arquivos mais recentes.">
        <View style={styles.dateTimeRow}>
          <View style={styles.dateTimeColumn}>
            <LabeledInput
              label="De"
              value={filterForm.performedFrom}
              onChangeText={(value) => setFilterForm((current) => ({ ...current, performedFrom: maskDateInput(value) }))}
              placeholder="01/01/2026"
              keyboardType="numeric"
              autoCapitalize="none"
            />
          </View>
          <View style={styles.dateTimeColumn}>
            <LabeledInput
              label="Até"
              value={filterForm.performedTo}
              onChangeText={(value) => setFilterForm((current) => ({ ...current, performedTo: maskDateInput(value) }))}
              placeholder="31/12/2026"
              keyboardType="numeric"
              autoCapitalize="none"
            />
          </View>
        </View>
        <View style={styles.rowGap}>
          {[
            { key: "recent_upload", title: "Arquivos recentes" },
            { key: "recent_exam", title: "Data mais recente" },
            { key: "oldest_exam", title: "Data mais antiga" },
          ].map((option) => (
            <SmallButton
              key={option.key}
              title={option.title}
              variant={filterForm.sort === option.key ? "primary" : "secondary"}
              onPress={() => setFilterForm((current) => ({ ...current, sort: option.key }))}
            />
          ))}
        </View>
        <View style={styles.rowGap}>
          <SmallButton title="Atualizar lista" onPress={() => setFilters({ ...filterForm })} />
          <SmallButton
            title="Limpar filtros"
            variant="secondary"
            onPress={() => {
              const clearedFilters = { performedFrom: "", performedTo: "", sort: "recent_upload" };
              setFilterForm(clearedFilters);
              setFilters({ ...clearedFilters });
            }}
          />
        </View>
      </SectionCard>
      <SectionCard title="Seus exames" subtitle="Veja os registros que você já salvou.">
        {items.map((item) => (
          <View key={item.id} style={styles.examCard}>
            <View style={styles.inlineHeader}>
              <Text style={styles.listTitle}>{item.title}</Text>
              <TonePill label={item.exam_type || "Exame"} tone="info" />
            </View>
            <Text style={styles.listSubtitle}>Realizado em {formatDate(item.performed_at)}</Text>
            {item.notes ? <Text style={styles.bodyText}>{item.notes}</Text> : null}
            <View style={styles.rowGap}>
              <TonePill label={item.file_url ? "Arquivo disponível" : "Arquivo pendente"} tone={item.file_url ? "success" : "neutral"} />
              <TonePill label={`Upload ${formatDateTime(item.uploaded_at)}`} tone="neutral" />
            </View>
            <View style={styles.rowGap}>
              <SmallButton title="Visualizar" onPress={() => openExam(item)} disabled={!item.file_url || deletingExamId === item.id} />
              <SmallButton title={deletingExamId === item.id ? "Apagando..." : "Apagar"} variant="danger" onPress={() => confirmDeleteExam(item)} disabled={deletingExamId === item.id} />
            </View>
          </View>
        ))}
        {!items.length && !loading ? <EmptyState title="Você ainda não enviou exames" description="Assim que enviar seu primeiro arquivo, ele vai aparecer aqui com a data e o tipo informado." /> : null}
      </SectionCard>
      </ScreenScroll>
      <Modal visible={Boolean(previewItem)} transparent animationType="slide" onRequestClose={() => setPreviewItem(null)}>
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, styles.examPreviewModalCard]}>
            <View style={styles.inlineHeader}>
              <View style={{ flex: 1 }}>
                <Text style={styles.cardTitle}>{previewItem?.title || "Visualizar exame"}</Text>
                <Text style={styles.cardSubtitle}>{previewItem ? `${previewItem.exam_type || "Exame"} - ${formatDate(previewItem.performed_at)}` : ""}</Text>
              </View>
              <SmallButton title="Fechar" variant="secondary" onPress={() => setPreviewItem(null)} />
            </View>
            {previewItem?.file_url ? (
              <Image source={{ uri: previewItem.file_url }} style={styles.examPreviewImage} resizeMode="contain" />
            ) : (
              <Text style={styles.bodyText}>Este exame nao tem um arquivo disponivel.</Text>
            )}
            <View style={styles.rowGap}>
              <SmallButton title="Abrir fora do app" onPress={() => previewItem?.file_url && openFileExternally(previewItem.file_url)} disabled={!previewItem?.file_url} />
              <SmallButton
                title={deletingExamId === previewItem?.id ? "Apagando..." : "Apagar"}
                variant="danger"
                onPress={() => previewItem && confirmDeleteExam(previewItem)}
                disabled={!previewItem || deletingExamId === previewItem.id}
              />
            </View>
          </View>
        </View>
      </Modal>
    </>
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
      Alert.alert("Não foi possível carregar seus ciclos", error.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, token]);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async () => {
    try {
      let s = form.start_date; let e = form.end_date;
      if(s && s.includes('/')) s = s.split('/').reverse().join('-');
      if(e && e.includes('/')) e = e.split('/').reverse().join('-');

      await apiRequest(apiUrl, "/api/patient/cycles/", { method: "POST", token, body: { ...form, start_date: s, end_date: e } });
      setForm({ start_date: "", end_date: "", symptoms: "", notes: "" });
      await load();
      Alert.alert("Ciclo registrado", "Seu ciclo foi salvo com sucesso.");
    } catch (error) {
      Alert.alert("Não foi possível registrar o ciclo", error.message);
    }
  };

  return (
    <ScreenScroll refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.screenContent}>
      <View style={{ backgroundColor: '#9A3838', padding: 20, borderRadius: 24, marginHorizontal: 24, marginTop: 16, marginBottom: 16 }}>
         <Text style={{ color: '#FFF', fontSize: 18, fontWeight: 'bold', marginBottom: 16 }}>Maio 2026</Text>
         <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
            {['D','S','T','Q','Q','S','S'].map((d, i) => <View key={`w-${i}`} style={{ width: '14.28%', alignItems: 'center', marginBottom: 8 }}><Text style={{ color: 'rgba(255,255,255,0.7)', fontWeight: 'bold' }}>{d}</Text></View>)}
            {Array.from({length: 31}, (_, i) => i + 1).map(d => (
               <View key={d} style={{ width: '14.28%', aspectRatio: 1, padding: 2 }}>
                  <View style={{ flex: 1, backgroundColor: d >= 12 && d <= 16 ? '#FFF' : 'transparent', borderRadius: 8, alignItems: 'center', justifyContent: 'center' }}>
                     <Text style={{ color: d >= 12 && d <= 16 ? '#9A3838' : '#FFF', fontWeight: 'bold' }}>{d}</Text>
                  </View>
               </View>
            ))}
         </View>
      </View>
      <SectionCard title="Registrar ciclo" subtitle="Guarde as datas para acompanhar seu ritmo com mais clareza.">
        <LabeledInput label="Início do ciclo (DD/MM/AAAA)" value={form.start_date} onChangeText={(value) => {
           let v = value.replace(/\D/g, "");
           if (v.length > 8) v = v.slice(0, 8);
           if (v.length >= 5) v = `${v.slice(0, 2)}/${v.slice(2, 4)}/${v.slice(4)}`;
           else if (v.length >= 3) v = `${v.slice(0, 2)}/${v.slice(2)}`;
           setForm((current) => ({ ...current, start_date: v }));
        }} placeholder="12/05/2026" keyboardType="numeric" />
        <LabeledInput label="Fim do ciclo (DD/MM/AAAA)" value={form.end_date} onChangeText={(value) => {
           let v = value.replace(/\D/g, "");
           if (v.length > 8) v = v.slice(0, 8);
           if (v.length >= 5) v = `${v.slice(0, 2)}/${v.slice(2, 4)}/${v.slice(4)}`;
           else if (v.length >= 3) v = `${v.slice(0, 2)}/${v.slice(2)}`;
           setForm((current) => ({ ...current, end_date: v }));
        }} placeholder="16/05/2026" keyboardType="numeric" />
        <LabeledInput label="Sintomas" value={form.symptoms} onChangeText={(value) => setForm((current) => ({ ...current, symptoms: value }))} placeholder="Ex.: fluxo médio" />
        <Pressable onPress={submit} style={styles.primaryAction}>
          <Text style={styles.primaryActionText}>Salvar ciclo</Text>
        </Pressable>
      </SectionCard>
      <SectionCard title="Seus registros">
        {items.map((item) => (
          <View key={item.id} style={styles.listItem}>
            <Text style={styles.listTitle}>De {formatDate(item.start_date)} a {formatDate(item.end_date)}</Text>
            <Text style={styles.listSubtitle}>{item.symptoms || "Sem sintomas informados."}</Text>
          </View>
        ))}
        {!items.length && !loading ? <EmptyState title="Nenhum ciclo registrado" description="Adicione seu primeiro ciclo para começar a montar um histórico mais útil para o seu acompanhamento." /> : null}
      </SectionCard>
      </ScreenScroll>
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
      Alert.alert("Não foi possível carregar seus acessos", error.message);
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
      const actionFeedback = {
        approve: "Você liberou o acesso com sucesso.",
        reject: "Você recusou este pedido de acesso.",
        revoke: "O acesso foi encerrado com sucesso.",
      };
      Alert.alert("Pedido atualizado", actionFeedback[action] || "O pedido foi atualizado com sucesso.");
    } catch (error) {
      Alert.alert("Não foi possível atualizar o pedido", error.message);
    }
  };

  return (
    <ScreenScroll refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.screenContent}>
      <ScreenIntro eyebrow="Permissões" title="Você decide quem pode acessar" subtitle="Cada autorização vale apenas para a profissional escolhida e pode ser encerrada quando você quiser." />
      <SectionCard title="Permissões de acesso" subtitle="Veja quem pediu acesso aos seus exames e decida com tranquilidade.">
        <View style={styles.metricsGrid}>
          <Metric label="Em análise" value={items.filter((item) => item.status === "pending").length} />
          <Metric label="Liberados" value={items.filter((item) => item.status === "approved").length} />
          <Metric label="Encerradas" value={items.filter((item) => item.status !== "pending" && item.status !== "approved").length} />
        </View>
      </SectionCard>
      <SectionCard title="Controle da paciente" subtitle="A aprovação vale só para a profissional escolhida, não para toda a instituição.">
        <Text style={styles.bodyText}>
          Se você aprovar, apenas aquela profissional do {INSTITUTION_NAME} poderá ver seus exames. Quando quiser, você pode encerrar o acesso aqui.
        </Text>
      </SectionCard>
      <SectionCard title="Pedidos recebidos">
        {items.map((item) => (
          <View key={item.id} style={styles.accessCard}>
            <View style={styles.inlineHeader}>
              <Text style={styles.listTitle}>{getProfessional(item)?.full_name || "Profissional CESMAC"}</Text>
              <TonePill label={item.status_label} tone={getAccessTone(item.status)} />
            </View>
            <Text style={styles.listSubtitle}>{formatProfessionalDetails(getProfessional(item))}</Text>
            <Text style={styles.listSubtitle}>Pedido feito em {formatDateTime(item.requested_at)}</Text>
            {item.request_note ? <Text style={styles.bodyText}>{item.request_note}</Text> : <Text style={styles.bodyText}>A profissional não deixou mensagem adicional.</Text>}
            <View style={styles.rowGap}>
              {item.status === "pending" ? (
                <>
                  <SmallButton title="Permitir" onPress={() => decide(item.id, "approve")} />
                  <SmallButton title="Não permitir" variant="danger" onPress={() => decide(item.id, "reject")} />
                </>
              ) : item.status === "approved" ? (
                <SmallButton title="Encerrar acesso" variant="danger" onPress={() => decide(item.id, "revoke")} />
              ) : null}
            </View>
          </View>
        ))}
        {!items.length && !loading ? <EmptyState title="Nenhum pedido recebido" description="Quando uma profissional solicitar acesso aos seus exames, você poderá aprovar ou recusar por aqui." /> : null}
      </SectionCard>
    </ScreenScroll>
  );
}

function AppointmentsScreen({ apiUrl, token }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [removingAppointmentId, setRemovingAppointmentId] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const appointments = await apiRequest(apiUrl, "/api/patient/appointments/", { token });
      setItems(appointments);
    } catch (error) {
      Alert.alert("Não foi possível carregar suas consultas", error.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, token]);

  useEffect(() => {
    load();
  }, [load]);

  const removeCancelledAppointment = async (item) => {
    try {
      setRemovingAppointmentId(item.id);
      await apiRequest(apiUrl, `/api/patient/appointments/${item.id}/`, { method: "DELETE", token });
      setItems((current) => current.filter((appointment) => appointment.id !== item.id));
      Alert.alert("Consulta removida", "A consulta cancelada saiu da sua lista.");
    } catch (error) {
      Alert.alert("Nao foi possivel remover a consulta", error.message);
    } finally {
      setRemovingAppointmentId(null);
    }
  };

  const confirmRemoveCancelledAppointment = (item) => {
    Alert.alert(
      "Remover consulta cancelada?",
      "Essa consulta vai sair da sua lista do aplicativo, mas o registro continua salvo no sistema.",
      [
        { text: "Voltar", style: "cancel" },
        { text: "Remover", style: "destructive", onPress: () => removeCancelledAppointment(item) },
      ],
    );
  };

  return (
    <ScreenScroll refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.screenContent}>
      <ScreenIntro eyebrow="Consultas" title="Acompanhe sua agenda pelo app" subtitle="Os agendamentos são feitos pela profissional. Aqui você acompanha horários, datas e atualizações." />
      <SectionCard title="Como funciona" subtitle={`No ${INSTITUTION_NAME}, a profissional registra a consulta e o aplicativo mostra tudo para você.`}>
        <Text style={styles.bodyText}>
          Se houver nova consulta, ajuste de horário ou cancelamento, você consegue acompanhar por aqui sem precisar criar o agendamento pelo aplicativo.
        </Text>
      </SectionCard>
      <SectionCard title="Consultas marcadas" subtitle="Acompanhe os compromissos mais recentes da sua agenda.">
        {items.map((item) => (
          <View key={item.id} style={styles.appointmentCard}>
            <View style={styles.rowGap}>
              <TonePill label={item.status_label || "Consulta"} tone={getAppointmentTone(item.status)} />
            </View>
            <Text style={styles.appointmentWhen}>{formatScheduledFor(item.scheduled_for)}</Text>
            <Text style={styles.listTitle}>{getProfessional(item)?.full_name || "Profissional CESMAC"}</Text>
            <Text style={styles.listSubtitle}>{formatProfessionalDetails(getProfessional(item))}</Text>
            <Text style={styles.listSubtitle}>{item.specialist}</Text>
            {item.status === "cancelled" ? (
              <View style={styles.rowGap}>
                <SmallButton
                  title={removingAppointmentId === item.id ? "Removendo..." : "Remover da lista"}
                  variant="secondary"
                  onPress={() => confirmRemoveCancelledAppointment(item)}
                  disabled={removingAppointmentId === item.id}
                />
              </View>
            ) : null}
          </View>
        ))}
        {!items.length && !loading ? <EmptyState title="Nenhuma consulta agendada" description="Quando uma profissional marcar uma consulta para você, ela vai aparecer aqui com data, horário e responsável." /> : null}
      </SectionCard>
    </ScreenScroll>
  );
}

function MessagesScreen({ apiUrl, token, user, focusedNotificationCreatedAt }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiRequest(apiUrl, "/api/patient/messages/", { token });
      setItems(data);
    } catch (error) {
      Alert.alert("Não foi possível carregar suas mensagens", error.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, token]);

  useEffect(() => {
    load();
  }, [load]);

  let focusedMessageId = null;
  if (focusedNotificationCreatedAt) {
    const targetTime = new Date(focusedNotificationCreatedAt).getTime();
    let bestDiff = Number.POSITIVE_INFINITY;
    items.forEach((item) => {
      const isIncoming = String(item.sender?.id) !== String(user?.id);
      if (!isIncoming) return;
      const itemTime = new Date(item.created_at).getTime();
      const diff = Math.abs(itemTime - targetTime);
      if (diff < bestDiff) {
        bestDiff = diff;
        focusedMessageId = item.id;
      }
    });
  }

  const orderedItems = focusedMessageId
    ? [
        ...items.filter((item) => item.id === focusedMessageId),
        ...items.filter((item) => item.id !== focusedMessageId),
      ]
    : items;

  return (
    <ScreenScroll refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.screenContent}>
      <ScreenIntro eyebrow="Mensagens" title="Leia o conteúdo enviado pela profissional" subtitle="As mensagens seguras ficam salvas aqui para você consultar quando precisar." />
      <SectionCard title="Canal seguro" subtitle="Veja orientações trocadas com profissionais que já têm seu acesso aprovado.">
        <Text style={styles.bodyText}>
          Sempre que chegar um aviso de nova mensagem, abra esta área para ver o conteúdo completo com mais calma.
        </Text>
      </SectionCard>
      <SectionCard title="Mensagens recebidas">
        {orderedItems.map((item) => {
          const isIncoming = String(item.sender?.id) !== String(user?.id);
          const counterpart = isIncoming ? item.sender : item.recipient;
          return (
            <View key={item.id} style={[styles.notificationCard, item.id === focusedMessageId && styles.focusedMessageCard]}>
              <View style={styles.inlineHeader}>
                <View style={styles.rowGap}>
                  <Text style={styles.listTitle}>{counterpart?.full_name || "Profissional CESMAC"}</Text>
                  {item.id === focusedMessageId ? <TonePill label="Mensagem atual" tone="warning" /> : null}
                </View>
                <TonePill label={isIncoming ? "Recebida" : "Enviada"} tone={isIncoming ? "info" : "neutral"} />
              </View>
              <Text style={styles.listSubtitle}>{formatProfessionalDetails(counterpart)}</Text>
              <Text style={styles.bodyText}>{item.body}</Text>
              <Text style={styles.notificationMeta}>{formatDateTime(item.created_at)}</Text>
            </View>
          );
        })}
        {!items.length && !loading ? <EmptyState title="Nenhuma mensagem segura" description="Quando uma profissional enviar orientações ou recados para você, o conteúdo completo aparecerá aqui." /> : null}
      </SectionCard>
    </ScreenScroll>
  );
}

function NotificationsScreen({ apiUrl, token, onOpenFaq, onOpenMessages, onOpenMessageNotification }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deletingNotificationId, setDeletingNotificationId] = useState(null);

  const deleteReadNotification = async (item) => {
    try {
      setDeletingNotificationId(item.id);
      await apiRequest(apiUrl, `/api/patient/notifications/${item.id}/`, { method: "DELETE", token });
      setItems((current) => current.filter((notification) => notification.id !== item.id));
      Alert.alert("Aviso apagado", "O aviso lido saiu da sua lista.");
    } catch (error) {
      Alert.alert("Nao foi possivel apagar o aviso", error.message);
    } finally {
      setDeletingNotificationId(null);
    }
  };

  const confirmDeleteReadNotification = (item) => {
    Alert.alert(
      "Apagar aviso?",
      "Esse aviso lido vai sair da sua lista.",
      [
        { text: "Voltar", style: "cancel" },
        { text: "Apagar", style: "destructive", onPress: () => deleteReadNotification(item) },
      ],
    );
  };

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiRequest(apiUrl, "/api/patient/notifications/", { token });
      setItems(data);
    } catch (error) {
      Alert.alert("Não foi possível carregar seus avisos", error.message);
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
      Alert.alert("Não foi possível marcar os avisos como lidos", error.message);
    }
  };

  return (
    <ScreenScroll refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.screenContent}>
      <ScreenIntro eyebrow="Avisos" title="Fique por dentro do que importa" subtitle="Aqui ficam mensagens importantes sobre exames, consultas, ciclo e segurança da sua conta." />
      <SectionCard title="Central de avisos" subtitle="Veja mensagens importantes sobre exames, ciclo, consultas e segurança da sua conta." right={<SmallButton title="Marcar todos" variant="secondary" onPress={markAllRead} />}>
        <View style={styles.metricsGrid}>
          <Metric label="Total" value={items.length} />
          <Metric label="Importantes" value={items.filter((item) => item.is_critical).length} />
          <Metric label="Não lidos" value={items.filter((item) => !item.read_at).length} />
        </View>
        <View style={styles.helpPrompt}>
          <Text style={styles.helpPromptText}>Se um aviso indicar nova mensagem da profissional, abra a área de Mensagens para ler o conteúdo completo. Para outras dúvidas, use a Ajuda.</Text>
          <View style={styles.rowGap}>
            <SmallButton title="Mensagens" onPress={onOpenMessages} />
            <SmallButton title="Abrir FAQ" variant="secondary" onPress={onOpenFaq} />
          </View>
        </View>
      </SectionCard>
      <SectionCard title="Seus avisos">
        {items.map((item) => {
          const canOpenMessage = isSecureMessageNotification(item);
          return (
            <Pressable
              key={item.id}
              disabled={!canOpenMessage}
              onPress={() => {
                if (canOpenMessage) onOpenMessageNotification(item);
              }}
              style={[
                styles.notificationCard,
                item.is_critical && styles.notificationCardCritical,
                canOpenMessage && styles.notificationCardInteractive,
              ]}
            >
              <View style={styles.inlineHeader}>
                <View style={styles.rowGap}>
                  <TonePill label={item.type_label} tone={getNotificationTone(item)} />
                  {item.is_critical ? <TonePill label="Importante" tone="danger" /> : null}
                  {!item.read_at ? <TonePill label="Nova" tone="warning" /> : null}
                  {canOpenMessage ? <TonePill label="Toque para abrir" tone="info" /> : null}
                </View>
              </View>
              <Text style={styles.notificationMessage}>{item.message}</Text>
              {canOpenMessage ? <Text style={styles.notificationHint}>Ao tocar aqui, você vai direto para a mensagem mais recente.</Text> : null}
              <Text style={styles.notificationMeta}>{formatDateTime(item.created_at)}</Text>
              {item.read_at ? (
                <View style={styles.rowGap}>
                  <SmallButton
                    title={deletingNotificationId === item.id ? "Apagando..." : "Apagar"}
                    variant="secondary"
                    onPress={(event) => {
                      event?.stopPropagation?.();
                      confirmDeleteReadNotification(item);
                    }}
                    disabled={deletingNotificationId === item.id}
                  />
                </View>
              ) : null}
            </Pressable>
          );
        })}
        {!items.length && !loading ? <EmptyState title="Nenhum aviso no momento" description="Quando houver novidades importantes para você, elas vão aparecer aqui." /> : null}
      </SectionCard>
    </ScreenScroll>
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
      Alert.alert("Não foi possível carregar a ajuda", error.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, token]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <ScreenScroll refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.screenContent}>
      <ScreenIntro eyebrow="Ajuda" title="Respostas rápidas quando surgir uma dúvida" subtitle="Consulte esta área sempre que quiser relembrar como usar o aplicativo ou entender um recurso." />
      <SectionCard title="Ajuda" subtitle="Respostas rápidas para as dúvidas mais comuns sobre o aplicativo.">
        <Text style={styles.bodyText}>Sempre que precisar relembrar como algo funciona, consulte esta área. As respostas podem ser atualizadas pela equipe responsável.</Text>
      </SectionCard>
      <SectionCard title="Perguntas frequentes">
        {items.map((item) => (
          <View key={item.id} style={styles.faqCard}>
            <Text style={styles.faqQuestion}>{item.question}</Text>
            <Text style={styles.faqAnswer}>{item.answer}</Text>
          </View>
        ))}
        {!items.length && !loading ? <EmptyState title="Ainda não há perguntas publicadas" description="Quando a equipe cadastrar respostas frequentes, elas vão aparecer aqui para consulta rápida." /> : null}
      </SectionCard>
    </ScreenScroll>
  );
}

export default function App() {
  const [booting, setBooting] = useState(true);
  const [apiUrl, setApiUrl] = useState("");
  const [token, setToken] = useState("");
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState("home");
  const [dashboard, setDashboard] = useState(null);
  const [, setRefreshingDashboard] = useState(false);
  const [settingsVisible, setSettingsVisible] = useState(false);
  const [draftApiUrl, setDraftApiUrl] = useState("");
  const [messageFocusCreatedAt, setMessageFocusCreatedAt] = useState(null);
  const [keyboardVisible, setKeyboardVisible] = useState(false);

  useEffect(() => {
    (async () => {
      const [savedUrl, savedToken, savedUser] = await Promise.all([
        getStoredValue(STORAGE_KEYS.apiUrl, LEGACY_STORAGE_KEYS.apiUrl),
        getStoredValue(STORAGE_KEYS.token, LEGACY_STORAGE_KEYS.token),
        getStoredValue(STORAGE_KEYS.user, LEGACY_STORAGE_KEYS.user),
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

  useEffect(() => {
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";
    const showSubscription = Keyboard.addListener(showEvent, () => setKeyboardVisible(true));
    const hideSubscription = Keyboard.addListener(hideEvent, () => setKeyboardVisible(false));

    return () => {
      showSubscription.remove();
      hideSubscription.remove();
    };
  }, []);

  const clearStoredSession = useCallback(async () => {
    setToken("");
    setUser(null);
    setDashboard(null);
    setMessageFocusCreatedAt(null);
    await AsyncStorage.multiRemove([
      STORAGE_KEYS.token,
      STORAGE_KEYS.user,
      LEGACY_STORAGE_KEYS.token,
      LEGACY_STORAGE_KEYS.user,
    ]);
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
      await clearStoredSession();
    }
  };

  const refreshDashboard = useCallback(async () => {
    if (!token || !apiUrl) return;
    try {
      setRefreshingDashboard(true);
      const data = await apiRequest(apiUrl, "/api/patient/dashboard/", { token });
      setDashboard(data);
    } catch (error) {
      if (error.status === 401) {
        await clearStoredSession();
        Alert.alert("Sessão expirada", "Seu acesso anterior não é mais válido para este endereço. Entre novamente.");
        return;
      }
      Alert.alert("Não foi possível atualizar seu painel", error.message);
    } finally {
      setRefreshingDashboard(false);
    }
  }, [apiUrl, token, clearStoredSession]);

  useEffect(() => {
    if (token && apiUrl) refreshDashboard();
  }, [token, apiUrl, refreshDashboard]);

  let activeScreen = (
    <NotificationsScreen
      apiUrl={apiUrl}
      token={token}
      onOpenFaq={() => setActiveTab("faq")}
      onOpenMessages={() => {
        setMessageFocusCreatedAt(null);
        setActiveTab("messages");
      }}
      onOpenMessageNotification={(notification) => {
        setMessageFocusCreatedAt(notification?.created_at || null);
        setActiveTab("messages");
      }}
    />
  );
  if (activeTab === "home") activeScreen = <DashboardScreen data={dashboard} refresh={refreshDashboard} />;
  if (activeTab === "exams") activeScreen = <ExamsScreen apiUrl={apiUrl} token={token} />;
  if (activeTab === "cycles") activeScreen = <CyclesScreen apiUrl={apiUrl} token={token} />;
  if (activeTab === "access") activeScreen = <AccessScreen apiUrl={apiUrl} token={token} />;
  if (activeTab === "messages") activeScreen = <MessagesScreen apiUrl={apiUrl} token={token} user={user} focusedNotificationCreatedAt={messageFocusCreatedAt} />;
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

  const firstName = user.full_name?.split(" ")[0] || "paciente";

  return (
    <LinearGradient colors={['#FCA5A5', '#E0F2FE']} style={styles.safeArea}>
      <SafeAreaView style={{flex: 1}}>
        <StatusBar style="dark" />
          <View style={{ paddingHorizontal: 20, paddingVertical: 10, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <View>
            <Text style={{ color: '#9A3838', fontSize: 22, fontWeight: '900' }}>Olá, {firstName}</Text>
          </View>
          <View style={{ flexDirection: 'row', gap: 10 }}>
             <SmallButton title="Sair" variant="danger" onPress={logout} />
          </View>
        </View>

      {activeScreen}

      {!keyboardVisible ? (
      <View style={{ position: 'absolute', bottom: 10, left: 10, right: 10 }}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ backgroundColor: 'rgba(255,255,255,0.98)', borderRadius: 999, paddingHorizontal: 8, paddingVertical: 8, gap: 10, borderWidth: 1, borderColor: '#F2D5D8', shadowColor: '#9A3838', shadowOpacity: 0.1, shadowRadius: 20, elevation: 5 }}>
          {NAV_ITEMS.map((item) => (
            <Pressable
              key={item.key}
              onPress={() => {
                if (item.key === "messages") setMessageFocusCreatedAt(null);
                setActiveTab(item.key);
              }}
              style={[{ paddingHorizontal: 16, paddingVertical: 10, borderRadius: 999, flexDirection: 'row', alignItems: 'center', gap: 6 }, activeTab === item.key && { backgroundColor: '#9A3838' }]}
            >
              <Ionicons name={item.icon} size={20} color={activeTab === item.key ? '#FFF' : '#8A5E63'} />
              <Text style={{ fontWeight: activeTab === item.key ? '800' : '700', color: activeTab === item.key ? '#FFF' : '#8A5E63' }}>{item.label}</Text>
            </Pressable>
          ))}
        </ScrollView>
      </View>
      ) : null}

      <Modal visible={settingsVisible} transparent animationType="slide">
        <KeyboardAvoidingView
          style={styles.modalBackdrop}
          behavior={Platform.OS === "ios" ? "padding" : "height"}
          keyboardVerticalOffset={Platform.OS === "ios" ? 0 : 20}
        >
          <View style={styles.modalCard}>
            <Text style={styles.cardTitle}>Ajustar conexão</Text>
            <Text style={styles.modalText}>Use o endereço em que o sistema está disponível para o aplicativo, como `http://192.168.0.15:8000`.</Text>
            <LabeledInput label="Endereço do sistema" value={draftApiUrl} onChangeText={setDraftApiUrl} autoCapitalize="none" placeholder="http://192.168.0.15:8000" />
            <View style={styles.rowGap}>
              <SmallButton title="Cancelar" variant="secondary" onPress={() => setSettingsVisible(false)} />
              <SmallButton
                title="Salvar"
                onPress={async () => {
                  const value = normalizeUrl(draftApiUrl);
                  const backendChanged = value !== normalizeUrl(apiUrl || "");
                  setApiUrl(value);
                  await AsyncStorage.setItem(STORAGE_KEYS.apiUrl, value);
                  if (backendChanged) {
                    await clearStoredSession();
                    Alert.alert("Endereço atualizado", "Por segurança, você vai precisar entrar novamente neste endereço.");
                  }
                  setSettingsVisible(false);
                }}
              />
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  flexFill: {
    flex: 1,
  },
  safeArea: {
    flex: 1,
    backgroundColor: "#FCEAEA",
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 28,
    padding: 24,
    gap: 16,
    marginBottom: 16,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 15,
    elevation: 3,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 16,
  },
  cardTitle: {
    color: "#4A2025",
    fontSize: 18,
    fontWeight: "800",
  },
  cardSubtitle: {
    marginTop: 4,
    color: "#8A5E63",
    lineHeight: 20,
  },
  smallButton: {
    backgroundColor: "#EAF1FF",
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 999,
    alignItems: "center",
  },
  secondaryButton: {
    backgroundColor: "#F2D5D8",
  },
  dangerButton: {
    backgroundColor: "#FFE1E1",
  },
  disabledAction: {
    opacity: 0.5,
  },
  smallButtonText: {
    color: "#1E6DDC",
    fontWeight: "700",
    fontSize: 13,
  },
  secondaryButtonText: {
    color: "#9A3838",
  },
  dangerButtonText: {
    color: "#B42318",
  },
  metricBox: {
    flexBasis: "46%",
    flexGrow: 1,
    backgroundColor: "#F9F5F5",
    borderRadius: 20,
    padding: 16,
    borderWidth: 1,
    borderColor: "#EAD6D6",
    gap: 4,
  },
  metricValue: {
    color: "#9A3838",
    fontSize: 24,
    fontWeight: "800",
  },
  metricLabel: {
    color: "#8A5E63",
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  tonePill: {
    alignSelf: "flex-start",
    backgroundColor: "#F9F5F5",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
  },
  tonePillSuccess: { backgroundColor: "#E6F4EA" },
  tonePillWarning: { backgroundColor: "#FFF3E0" },
  tonePillDanger: { backgroundColor: "#FCE8E6" },
  tonePillInfo: { backgroundColor: "#EAF1FF" },
  tonePillText: { color: "#8A5E63", fontSize: 12, fontWeight: "700" },
  tonePillTextSuccess: { color: "#137333" },
  tonePillTextWarning: { color: "#E65100" },
  tonePillTextDanger: { color: "#B31412" },
  tonePillTextInfo: { color: "#1E6DDC" },
  inputGroup: {
    gap: 8,
  },
  label: {
    color: "#8A5E63",
    fontSize: 14,
    fontWeight: "700",
    marginLeft: 4,
  },
  input: {
    backgroundColor: "#F9F5F5",
    borderWidth: 1,
    borderColor: "#EAD6D6",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    color: "#4A2025",
  },
  screenIntro: {
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 24,
    gap: 8,
  },
  screenIntroEyebrow: {
    color: "#A85E5E",
    fontSize: 12,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  screenIntroTitle: {
    color: "#4A2025",
    fontSize: 28,
    fontWeight: "900",
    letterSpacing: -0.5,
  },
  screenIntroText: {
    color: "#8A5E63",
    fontSize: 16,
    lineHeight: 24,
  },
  screenIntroFooter: {
    marginTop: 8,
  },
  screenIntroBadgeRow: {
    flexDirection: "row",
    gap: 8,
    flexWrap: "wrap",
  },
  emptyState: {
    backgroundColor: "#FFF",
    borderRadius: 24,
    borderWidth: 2,
    borderColor: "#F2D5D8",
    borderStyle: "dashed",
    padding: 32,
    gap: 12,
    alignItems: "center",
  },
  emptyStateTitle: {
    color: "#4A2025",
    fontSize: 16,
    fontWeight: "800",
    textAlign: "center",
  },
  emptyStateText: {
    color: "#8A5E63",
    lineHeight: 22,
    textAlign: "center",
  },
  authContainer: {
    flexGrow: 1,
    justifyContent: "flex-end",
  },
  eyebrow: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1,
    paddingHorizontal: 24,
    marginTop: 40,
    opacity: 0.9,
  },
  heroTitle: {
    color: "#FFFFFF",
    fontSize: 40,
    fontWeight: "900",
    letterSpacing: -1,
    paddingHorizontal: 24,
    marginTop: 8,
    textShadowColor: "rgba(0,0,0,0.1)",
    textShadowOffset: {width: 0, height: 2},
    textShadowRadius: 4,
  },
  heroText: {
    color: "#FFFFFF",
    fontSize: 17,
    lineHeight: 26,
    paddingHorizontal: 24,
    marginTop: 12,
    marginBottom: 30,
    opacity: 0.95,
  },
  authBenefitGrid: {
    paddingHorizontal: 24,
    gap: 12,
    marginBottom: 30,
  },
  authBenefitCard: {
    backgroundColor: "rgba(255,255,255,0.15)",
    borderRadius: 20,
    padding: 16,
  },
  authBenefitTitle: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "800",
    marginBottom: 4,
  },
  authBenefitText: {
    color: "rgba(255,255,255,0.9)",
    fontSize: 14,
    lineHeight: 20,
  },
  bodyText: {
    color: "#8A5E63",
    lineHeight: 24,
  },
  modeRow: {
    flexDirection: "row",
    backgroundColor: "#F9F5F5",
    borderRadius: 999,
    padding: 6,
    marginBottom: 24,
    marginHorizontal: 24,
  },
  modeButton: {
    flex: 1,
    paddingVertical: 12,
    alignItems: "center",
    borderRadius: 999,
  },
  modeButtonActive: {
    backgroundColor: "#FFFFFF",
    shadowColor: "#9A3838",
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 2,
  },
  modeButtonText: {
    color: "#8A5E63",
    fontWeight: "700",
  },
  modeButtonTextActive: {
    color: "#9A3838",
    fontWeight: "800",
  },
  primaryAction: {
    backgroundColor: "#9A3838",
    paddingVertical: 18,
    borderRadius: 999,
    alignItems: "center",
    marginTop: 16,
    shadowColor: "#9A3838",
    shadowOpacity: 0.3,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 4,
  },
  primaryActionText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "800",
  },
  screenContent: {
    paddingBottom: 100,
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  listItem: {
    borderTopWidth: 1,
    borderTopColor: "#F2D5D8",
    paddingTop: 16,
    gap: 6,
  },
  listTitle: {
    color: "#4A2025",
    fontSize: 16,
    fontWeight: "800",
  },
  listSubtitle: {
    color: "#8A5E63",
    lineHeight: 20,
  },
  sectionStep: {
    color: "#9A3838",
    fontSize: 15,
    fontWeight: "800",
    marginBottom: 8,
    marginTop: 8,
  },
  uploadCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    backgroundColor: "#F9F5F5",
    borderRadius: 24,
    borderWidth: 2,
    borderColor: "#F2D5D8",
    borderStyle: "dashed",
    padding: 20,
  },
  uploadCardSelected: {
    backgroundColor: "#FFFFFF",
    borderColor: "#9A3838",
    borderStyle: "solid",
  },
  uploadIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#F2D5D8",
    color: "#9A3838",
    textAlign: "center",
    textAlignVertical: "center",
    fontSize: 24,
    fontWeight: "700",
    overflow: "hidden",
  },
  uploadTitle: {
    color: "#4A2025",
    fontSize: 16,
    fontWeight: "800",
  },
  uploadSubtitle: {
    marginTop: 4,
    color: "#8A5E63",
    lineHeight: 20,
  },
  helpPrompt: {
    marginTop: 4,
    backgroundColor: "#F9F5F5",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#F2D5D8",
    padding: 16,
    gap: 10,
  },
  helpPromptText: {
    color: "#8A5E63",
    lineHeight: 22,
  },
  choiceCard: {
    backgroundColor: "#F9F5F5",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#EAD6D6",
    padding: 16,
    gap: 8,
  },
  choiceCardActive: {
    backgroundColor: "#9A3838",
    borderColor: "#9A3838",
  },
  choiceTitle: {
    color: "#4A2025",
    fontSize: 16,
    fontWeight: "800",
  },
  choiceTitleActive: {
    color: "#FFFFFF",
  },
  choiceSubtitle: {
    color: "#8A5E63",
  },
  choiceSubtitleActive: {
    color: "#F2D5D8",
  },
  choiceBadge: {
    alignSelf: "flex-start",
    backgroundColor: "#F2D5D8",
    color: "#9A3838",
    borderRadius: 999,
    overflow: "hidden",
    paddingHorizontal: 12,
    paddingVertical: 6,
    fontSize: 12,
    fontWeight: "800",
  },
  choiceBadgeActive: {
    backgroundColor: "#FFFFFF",
    color: "#9A3838",
  },
  dateTimeRow: {
    flexDirection: "row",
    gap: 12,
  },
  dateTimeColumn: {
    flex: 1,
  },
  previewCard: {
    backgroundColor: "#FFF",
    borderRadius: 24,
    padding: 20,
    gap: 8,
    borderWidth: 1,
    borderColor: "#F2D5D8",
    shadowColor: "#9A3838",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 2,
  },
  previewEyebrow: {
    color: "#A85E5E",
    fontSize: 12,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  previewHeadline: {
    color: "#4A2025",
    fontSize: 18,
    fontWeight: "800",
  },
  previewText: {
    color: "#4A2025",
    fontSize: 16,
    fontWeight: "700",
  },
  previewCaption: {
    color: "#8A5E63",
    lineHeight: 22,
  },
  examCard: {
    borderTopWidth: 1,
    borderTopColor: "#F2D5D8",
    paddingTop: 16,
    gap: 8,
  },
  accessCard: {
    borderTopWidth: 1,
    borderTopColor: "#F2D5D8",
    paddingTop: 16,
    gap: 8,
  },
  appointmentCard: {
    borderTopWidth: 1,
    borderTopColor: "#F2D5D8",
    paddingTop: 16,
    gap: 8,
  },
  appointmentWhen: {
    alignSelf: "flex-start",
    backgroundColor: "#F2D5D8",
    color: "#9A3838",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    overflow: "hidden",
    fontWeight: "800",
    fontSize: 13,
  },
  notificationCard: {
    borderTopWidth: 1,
    borderTopColor: "#F2D5D8",
    paddingTop: 16,
    gap: 8,
  },
  notificationCardInteractive: {
    borderRadius: 16,
    paddingHorizontal: 8,
    marginHorizontal: -8,
  },
  notificationCardCritical: {
    backgroundColor: "#FCE8E6",
    marginHorizontal: -8,
    paddingHorizontal: 8,
    borderRadius: 16,
  },
  focusedMessageCard: {
    backgroundColor: "#FFF7E8",
    borderRadius: 16,
    paddingHorizontal: 8,
    marginHorizontal: -8,
  },
  notificationMessage: {
    color: "#4A2025",
    fontSize: 16,
    fontWeight: "700",
    lineHeight: 24,
  },
  notificationHint: {
    color: "#9A3838",
    fontSize: 13,
    fontWeight: "700",
    lineHeight: 20,
  },
  notificationMeta: {
    color: "#8A5E63",
    fontSize: 13,
    fontWeight: "700",
  },
  faqCard: {
    borderTopWidth: 1,
    borderTopColor: "#F2D5D8",
    paddingTop: 16,
    gap: 8,
  },
  faqQuestion: {
    color: "#4A2025",
    fontSize: 17,
    fontWeight: "800",
    lineHeight: 24,
  },
  faqAnswer: {
    color: "#8A5E63",
    lineHeight: 24,
  },
  appHeaderShell: {
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 10,
    gap: 12,
  },
  appHeader: {
    backgroundColor: "#FFFFFF",
    borderRadius: 32,
    paddingHorizontal: 20,
    paddingVertical: 20,
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 16,
    alignItems: "flex-start",
    borderWidth: 1,
    borderColor: "#F2D5D8",
    shadowColor: "#9A3838",
    shadowOpacity: 0.08,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 10 },
    elevation: 5,
  },
  appHeaderCopy: {
    flex: 1,
  },
  appTitle: {
    fontSize: 28,
    fontWeight: "900",
    color: "#4A2025",
    letterSpacing: -0.5,
  },
  appSubtitle: {
    marginTop: 6,
    color: "#8A5E63",
    lineHeight: 22,
  },
  appMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 8,
  },
  appMetaText: {
    flex: 1,
    color: "#8A5E63",
    fontSize: 13,
    fontWeight: "700",
  },
  headerStatusText: {
    color: "#9A3838",
    fontSize: 13,
    fontWeight: "800",
  },
  headerStack: {
    gap: 10,
  },
  bottomNav: {
    position: "absolute",
    bottom: 20,
    left: 20,
    right: 20,
    backgroundColor: "rgba(255,255,255,0.98)",
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 12,
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    gap: 6,
    borderWidth: 1,
    borderColor: "#F2D5D8",
    shadowColor: "#9A3838",
    shadowOpacity: 0.1,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 10 },
    elevation: 8,
  },
  navItem: {
    flexBasis: "22%",
    minWidth: 0,
    paddingVertical: 12,
    paddingHorizontal: 8,
    borderRadius: 999,
    alignItems: "center",
  },
  navItemActive: {
    backgroundColor: "#9A3838",
  },
  navText: {
    color: "#8A5E63",
    fontWeight: "700",
    fontSize: 11,
    marginTop: 4,
  },
  navTextActive: {
    color: "#FFFFFF",
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(74,32,37,0.6)",
    justifyContent: "flex-end",
  },
  modalCard: {
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 36,
    borderTopRightRadius: 36,
    padding: 30,
    gap: 16,
  },
  modalText: {
    color: "#8A5E63",
    lineHeight: 24,
    fontSize: 16,
  },
  examPreviewModalCard: {
    maxHeight: "85%",
  },
  examPreviewImage: {
    width: "100%",
    height: 360,
    borderRadius: 24,
    backgroundColor: "#F9F5F5",
  },
  inlineHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  rowGap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  }
});

