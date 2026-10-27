import type { AgentConfig, ChatResponse, Message } from "../types/chat";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function getAgentConfig(): Promise<AgentConfig> {
  const response = await fetch(`${API_BASE_URL}/api/config`);
  if (!response.ok) throw new Error("Agent configuration unavailable");
  return response.json() as Promise<AgentConfig>;
}

export async function sendMessage(message: string, history: Message[]): Promise<ChatResponse> {
  const safeHistory = history
    .filter((item) => item.text.trim().length > 0)
    .slice(-20)
    .map(({ role, text }) => ({ role, text: text.trim().slice(0, 4000) }));
  const response = await fetch(`${API_BASE_URL}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: message.trim().slice(0, 4000), history: safeHistory }) });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { detail?: string | Array<{ msg?: string }> };
    const detail = Array.isArray(payload.detail) ? payload.detail.map((item) => item.msg).filter(Boolean).join(" ") : payload.detail;
    throw new Error(detail ?? "ସହାୟକଙ୍କ ସହିତ ଯୋଗାଯୋଗ ହୋଇପାରିଲା ନାହିଁ।");
  }
  return response.json() as Promise<ChatResponse>;
}

export async function transcribeAudio(audio: Blob, language = "od-IN"): Promise<{ text: string; language: string; confidence?: number }> {
  const body = new FormData();
  body.append("audio", audio, "recording.webm");
  body.append("language", language);
  const response = await fetch(`${API_BASE_URL}/api/stt`, { method: "POST", body });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { detail?: string };
    throw new Error(payload.detail ?? "ଭଏସ୍ ବୁଝିହେଲା ନାହିଁ।");
  }
  return response.json() as Promise<{ text: string; language: string; confidence?: number }>;
}

export async function synthesizeSpeech(text: string, speaker: string, language = "od-IN"): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/api/tts`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, speaker, language_code: language }) });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { detail?: string };
    throw new Error(payload.detail ?? "ଭଏସ୍ ତିଆରି ହୋଇପାରିଲା ନାହିଁ।");
  }
  return response.blob();
}
