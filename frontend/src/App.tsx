import { useEffect, useRef, useState } from "react";
import { ArrowUp, ChevronDown, MessageCircle, Mic, Phone, RotateCcw, Sparkles, User, UserRound, X } from "lucide-react";
import { ChatMessage } from "./components/ChatMessage";
import { getAgentConfig, sendMessage, synthesizeSpeech, transcribeAudio } from "./services/api";
import type { LanguageCode, Message } from "./types/chat";
import "./styles.css";

type VoiceOption = { id: string; name: string; gender: "male" | "female"; sarvamSpeaker: string };
type VoiceTurnMode = "manual" | "call";
type CallLanguage = LanguageCode;
const VOICE_OPTIONS: VoiceOption[] = [
  { id: "sangram", name: "Sangram", gender: "male", sarvamSpeaker: "shubh" },
  { id: "rajesh", name: "Rajesh", gender: "male", sarvamSpeaker: "rahul" },
  { id: "lipsa", name: "Lipsa", gender: "female", sarvamSpeaker: "ritu" },
  { id: "gayatri", name: "Gayatri", gender: "female", sarvamSpeaker: "pooja" },
  { id: "arpita", name: "Arpita", gender: "female", sarvamSpeaker: "neha" },
];
const DEFAULT_AGENT_NAME = "Odisha AI";
const DEFAULT_AGENT_TAGLINE = "ଓଡ଼ିଶା ବିଷୟରେ ପଚାରନ୍ତୁ";
const createWelcome = (name: string, tagline: string): Message => ({ role: "assistant", text: `ନମସ୍କାର! ମୁଁ ${name}। ${tagline}` });
const CALL_SILENCE_MS = 1300;
const CALL_HOLD_MS = 12000;
const CALL_SPEECH_THRESHOLD = 0.035;
const CALL_MOBILE_BARGE_IN_THRESHOLD = 0.08;
const CALL_BARGE_IN_CONFIRMATION_MS = 500;
const isMobileDevice = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
const SILENT_AUDIO_URL = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=";
const createCallGreeting = (name: string) => `ନମସ୍କାର! ମୁଁ ${name}। ଆପଣଙ୍କୁ ସ୍ୱାଗତ। ଆପଣ ଓଡ଼ିଆରେ କଥା ହେବେ କି ଇଂରାଜୀରେ? ଦୟାକରି ଓଡ଼ିଆ କିମ୍ବା ଇଂରାଜୀ କୁହନ୍ତୁ।`;
const CALL_LANGUAGE_RETRY = "ଦୟାକରି ଓଡ଼ିଆ କିମ୍ବା ଇଂରାଜୀ ମଧ୍ୟରୁ ଆପଣଙ୍କ ପସନ୍ଦ କୁହନ୍ତୁ।";
const CALL_IDLE_PROMPTS: Record<CallLanguage, string[]> = {
  "od-IN": ["ଆପଣ ଅଛନ୍ତି କି? ମୁଁ ଆପଣଙ୍କ କଥା ଶୁଣିବାକୁ ପ୍ରସ୍ତୁତ।", "ଆପଣଙ୍କ ପ୍ରଶ୍ନ କୁହନ୍ତୁ, ମୁଁ ଶୁଣୁଛି।", "କିଛି ପଚାରିବାକୁ ଚାହୁଁଛନ୍ତି କି?"],
  "en-IN": ["Are you still there? I’m listening.", "Take your time. What would you like to ask?", "Would you like to ask me something about Odisha?"],
};

function VoiceIcon({ gender }: { gender: VoiceOption["gender"] }) {
  return gender === "male" ? <User size={17} /> : <UserRound size={17} />;
}

function VoicePicker({ selected, onChange }: { selected: VoiceOption; onChange: (voice: VoiceOption) => void }) {
  const [open, setOpen] = useState(false);
  return <div className="voice-picker">
    <button className="voice-picker-trigger" type="button" onClick={() => setOpen((current) => !current)} aria-expanded={open}>
      <span className={`voice-icon ${selected.gender}`}><VoiceIcon gender={selected.gender} /></span><span>{selected.name}</span><ChevronDown size={15} />
    </button>
    {open && <div className="voice-menu" role="menu">{VOICE_OPTIONS.map((voice) => <button key={voice.id} className={`voice-option ${voice.id === selected.id ? "selected" : ""}`} type="button" onClick={() => { onChange(voice); setOpen(false); }} role="menuitem"><span className={`voice-icon ${voice.gender}`}><VoiceIcon gender={voice.gender} /></span><span>{voice.name}</span></button>)}</div>}
  </div>;
}

export default function App() {
  const [isOpen, setIsOpen] = useState(false);
  const [isCallMode, setIsCallMode] = useState(false);
  const [showCallPrompt, setShowCallPrompt] = useState(false);
  const [callSeconds, setCallSeconds] = useState(0);
  const [agentName, setAgentName] = useState(DEFAULT_AGENT_NAME);
  const [agentTagline, setAgentTagline] = useState(DEFAULT_AGENT_TAGLINE);
  const [messages, setMessages] = useState<Message[]>([createWelcome(DEFAULT_AGENT_NAME, DEFAULT_AGENT_TAGLINE)]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [voiceState, setVoiceState] = useState<"idle" | "listening" | "processing" | "speaking">("idle");
  const [voiceId, setVoiceId] = useState("sangram");
  const [callLanguage, setCallLanguage] = useState<CallLanguage>("od-IN");
  const [speakingIndex, setSpeakingIndex] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const vadFrameRef = useRef<number | null>(null);
  const callIdleTimerRef = useRef<number | null>(null);
  const callModeRef = useRef(false);
  const callLanguageRef = useRef<CallLanguage>("od-IN");
  const languageChoicePendingRef = useRef(false);
  const idlePromptIndexRef = useRef(0);
  const bargeInStreamRef = useRef<MediaStream | null>(null);
  const bargeInContextRef = useRef<AudioContext | null>(null);
  const bargeInFrameRef = useRef<number | null>(null);
  const speechDetectedRef = useRef(false);
  const silenceStartedAtRef = useRef<number | null>(null);
  const selectedVoice = VOICE_OPTIONS.find((voice) => voice.id === voiceId) ?? VOICE_OPTIONS[0];

  useEffect(() => {
    void getAgentConfig().then((config) => {
      setAgentName(config.name); setAgentTagline(config.tagline);
      setMessages((current) => current.length === 1 && current[0].text === createWelcome(DEFAULT_AGENT_NAME, DEFAULT_AGENT_TAGLINE).text ? [createWelcome(config.name, config.tagline)] : current);
    }).catch(() => { /* The fallback identity keeps the widget usable if config is unavailable. */ });
  }, []);

  useEffect(() => {
    if (!isCallMode) return;
    const timer = window.setInterval(() => setCallSeconds((current) => current + 1), 1000);
    return () => window.clearInterval(timer);
  }, [isCallMode]);

  function clearCallIdleTimer() {
    if (callIdleTimerRef.current !== null) window.clearTimeout(callIdleTimerRef.current);
    callIdleTimerRef.current = null;
  }

  function cleanupBargeInMonitor() {
    if (bargeInFrameRef.current !== null) window.cancelAnimationFrame(bargeInFrameRef.current);
    bargeInFrameRef.current = null;
    bargeInStreamRef.current?.getTracks().forEach((track) => track.stop());
    bargeInStreamRef.current = null;
    if (bargeInContextRef.current) void bargeInContextRef.current.close();
    bargeInContextRef.current = null;
  }

  function detectPreferredLanguage(text: string): CallLanguage | null {
    if (/\benglish\b|ଇଂରାଜୀ/i.test(text)) return "en-IN";
    if (/\bodia\b|ଓଡ଼ିଆ|ଓଡିଆ/i.test(text)) return "od-IN";
    return null;
  }

  function setCallLanguagePreference(language: CallLanguage) {
    callLanguageRef.current = language;
    setCallLanguage(language);
    languageChoicePendingRef.current = false;
  }

  function cleanupAudioInput(discardRecorder = false) {
    if (vadFrameRef.current !== null) window.cancelAnimationFrame(vadFrameRef.current);
    vadFrameRef.current = null;
    clearCallIdleTimer();
    if (discardRecorder && recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.onstop = null;
      recorderRef.current.stop();
    }
    recorderRef.current = null;
    recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
    recordingStreamRef.current = null;
    if (audioContextRef.current) void audioContextRef.current.close();
    audioContextRef.current = null;
  }

  function stopPlayback() {
    cleanupBargeInMonitor();
    audioRef.current?.pause();
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    audioUrlRef.current = null; setSpeakingIndex(null);
    setVoiceState((current) => current === "speaking" ? "idle" : current);
  }
  async function unlockMobileAudio() {
    if (!isMobileDevice || audioRef.current) return;
    const audio = new Audio();
    audio.setAttribute("playsinline", "true");
    audio.muted = true;
    audio.src = SILENT_AUDIO_URL;
    try {
      await audio.play();
      audio.pause();
      audio.currentTime = 0;
      audioRef.current = audio;
    } catch {
      // The normal playback path will provide the user-facing error if needed.
    }
  }
  function resetConversation() { stopPlayback(); setMessages([createWelcome(agentName, agentTagline)]); setError(""); }
  function openCallPrompt() { stopPlayback(); setShowCallPrompt(true); }
  async function startCall() {
    // Request permission directly from the call button gesture. Mobile browsers
    // may reject a later getUserMedia call started after the greeting finishes.
    if (!window.isSecureContext) {
      setError("ସୁରକ୍ଷିତ HTTPS ସଂଯୋଗରେ ମାଇକ୍ରୋଫୋନ୍ ବ୍ୟବହାର କରନ୍ତୁ।");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("ଏହି ବ୍ରାଉଜରରେ ମାଇକ୍ରୋଫୋନ୍ ସମର୍ଥିତ ନୁହେଁ।");
      return;
    }
    void unlockMobileAudio();
    try {
      const permissionStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      permissionStream.getTracks().forEach((track) => track.stop());
    } catch {
      setError("ମାଇକ୍ରୋଫୋନ୍ ଅନୁମତି ଦିଅନ୍ତୁ ଏବଂ ପୁଣି କଲ୍ ଆରମ୍ଭ କରନ୍ତୁ।");
      return;
    }
    setShowCallPrompt(false); setIsCallMode(true); setCallSeconds(0); setError("");
    callModeRef.current = true;
    callLanguageRef.current = "od-IN";
    setCallLanguage("od-IN");
    languageChoicePendingRef.current = true;
    idlePromptIndexRef.current = 0;
    window.setTimeout(() => { void playSpeech(createCallGreeting(agentName), -1, true, "od-IN"); }, 0);
  }
  function endCall() {
    callModeRef.current = false;
    cleanupAudioInput(true);
    cleanupBargeInMonitor();
    if (voiceState === "speaking") stopPlayback();
    setIsCallMode(false); setVoiceState("idle");
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault(); const text = input.trim(); if (!text || loading) return;
    setInput(""); setError(""); setMessages((current) => [...current, { role: "user", text }]); setLoading(true);
    try { const result = await sendMessage(text, messages); setMessages((current) => [...current, { role: "assistant", text: result.reply, language: result.language }]); }
    catch (err) { setError(err instanceof Error ? err.message : "କିଛି ଭୁଲ୍ ହୋଇଛି।"); }
    finally { setLoading(false); }
  }

  function scheduleCallIdlePrompt() {
    clearCallIdleTimer();
    if (!callModeRef.current) return;
    callIdleTimerRef.current = window.setTimeout(() => {
      if (callModeRef.current && recorderRef.current) {
        cleanupAudioInput(true);
        const prompts = CALL_IDLE_PROMPTS[callLanguageRef.current];
        const prompt = prompts[idlePromptIndexRef.current % prompts.length];
        idlePromptIndexRef.current += 1;
        void playSpeech(prompt, -1, true, callLanguageRef.current);
      }
    }, CALL_HOLD_MS);
  }

  function cleanupTurnInput() {
    if (vadFrameRef.current !== null) window.cancelAnimationFrame(vadFrameRef.current);
    vadFrameRef.current = null;
    clearCallIdleTimer();
    recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
    recordingStreamRef.current = null;
    if (audioContextRef.current) void audioContextRef.current.close();
    audioContextRef.current = null;
  }

  async function monitorBargeIn() {
    // Mobile browsers often reject a second microphone stream while audio is
    // playing. The primary call recorder starts after playback completes.
    if (isMobileDevice || !callModeRef.current || !audioRef.current) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      if (!callModeRef.current || !audioRef.current) { stream.getTracks().forEach((track) => track.stop()); return; }
      const audioContext = new AudioContext();
      const analyser = audioContext.createAnalyser(); analyser.fftSize = 2048;
      audioContext.createMediaStreamSource(stream).connect(analyser);
      bargeInStreamRef.current = stream; bargeInContextRef.current = audioContext;
      const samples = new Uint8Array(analyser.fftSize);
      let speechStartedAt: number | null = null;
      const bargeInThreshold = isMobileDevice ? CALL_MOBILE_BARGE_IN_THRESHOLD : CALL_SPEECH_THRESHOLD;
      const monitor = () => {
        if (!callModeRef.current || !audioRef.current) { cleanupBargeInMonitor(); return; }
        analyser.getByteTimeDomainData(samples);
        let sum = 0; for (const sample of samples) { const normalized = (sample - 128) / 128; sum += normalized * normalized; }
        if (Math.sqrt(sum / samples.length) > bargeInThreshold) {
          speechStartedAt ??= performance.now();
          if (performance.now() - speechStartedAt >= CALL_BARGE_IN_CONFIRMATION_MS) {
            cleanupBargeInMonitor(); stopPlayback(); void startCallListening(); return;
          }
        } else speechStartedAt = null;
        bargeInFrameRef.current = window.requestAnimationFrame(monitor);
      };
      bargeInFrameRef.current = window.requestAnimationFrame(monitor);
    } catch {
      // Barge-in is an enhancement; the call continues if a second mic monitor is unavailable.
    }
  }

  async function startRecording(mode: VoiceTurnMode) {
    if (!navigator.mediaDevices?.getUserMedia) { setError("ଏହି ବ୍ରାଉଜରରେ ମାଇକ୍ରୋଫୋନ୍ ସମର୍ଥିତ ନୁହେଁ।"); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];
      recordingStreamRef.current = stream;
      speechDetectedRef.current = false;
      silenceStartedAtRef.current = null;
      recorder.ondataavailable = (event) => { if (event.data.size) audioChunksRef.current.push(event.data); };
      recorder.onstop = async () => {
        cleanupTurnInput(); recorderRef.current = null;
        if (mode === "call" && !callModeRef.current) return;
        setVoiceState("processing");
        try {
          const result = await transcribeAudio(new Blob(audioChunksRef.current, { type: recorder.mimeType || "audio/webm" }), mode === "call" ? callLanguageRef.current : "od-IN");
          await runVoiceTurn(result.text, messages, mode);
        } catch (err) {
          setError(err instanceof Error ? err.message : "ଭଏସ୍ ବୁଝିହେଲା ନାହିଁ।");
          if (mode === "call" && callModeRef.current) window.setTimeout(() => { void startCallListening(); }, 700);
        } finally {
          if (mode === "manual") setVoiceState((current) => current === "speaking" ? current : "idle");
        }
      };
      recorderRef.current = recorder; recorder.start(); setError(""); setVoiceState("listening");
      if (mode === "manual") {
        window.setTimeout(() => { if (recorder.state === "recording") recorder.stop(); }, 30000);
        return;
      }
      const audioContext = new AudioContext();
      const analyser = audioContext.createAnalyser(); analyser.fftSize = 2048;
      audioContext.createMediaStreamSource(stream).connect(analyser); audioContextRef.current = audioContext;
      const samples = new Uint8Array(analyser.fftSize);
      const monitor = () => {
        if (recorder.state !== "recording" || !callModeRef.current) return;
        analyser.getByteTimeDomainData(samples);
        let sum = 0; for (const sample of samples) { const normalized = (sample - 128) / 128; sum += normalized * normalized; }
        const isSpeech = Math.sqrt(sum / samples.length) > CALL_SPEECH_THRESHOLD;
        if (isSpeech) { speechDetectedRef.current = true; silenceStartedAtRef.current = null; clearCallIdleTimer(); }
        else if (speechDetectedRef.current) {
          silenceStartedAtRef.current ??= performance.now();
          if (performance.now() - silenceStartedAtRef.current >= CALL_SILENCE_MS) { recorder.stop(); return; }
        }
        vadFrameRef.current = window.requestAnimationFrame(monitor);
      };
      vadFrameRef.current = window.requestAnimationFrame(monitor); scheduleCallIdlePrompt();
    } catch {
      setError(window.isSecureContext ? "ମାଇକ୍ରୋଫୋନ୍ ଅନୁମତି ମିଳିଲା ନାହିଁ। ବ୍ରାଉଜର୍ ସେଟିଂସ୍‌ରେ ମାଇକ୍ ଅନୁମତି ଯାଞ୍ଚ କରନ୍ତୁ।" : "ସୁରକ୍ଷିତ HTTPS ସଂଯୋଗରେ ମାଇକ୍ରୋଫୋନ୍ ବ୍ୟବହାର କରନ୍ତୁ।");
      if (mode === "call") setVoiceState("idle");
    }
  }

  async function startCallListening() {
    if (!callModeRef.current || recorderRef.current) return;
    await startRecording("call");
  }

  async function toggleRecording() {
    if (voiceState === "speaking") { stopPlayback(); return; }
    if (voiceState === "listening") { recorderRef.current?.stop(); return; }
    void unlockMobileAudio();
    await startRecording(isCallMode ? "call" : "manual");
  }

  async function playSpeech(text: string, index: number, continueCall = false, language: CallLanguage = callLanguageRef.current) {
    stopPlayback(); setError("");
    try {
      const audio = audioRef.current ?? new Audio();
      audioRef.current = audio;
      audio.src = URL.createObjectURL(await synthesizeSpeech(text, selectedVoice.sarvamSpeaker, language));
      audio.muted = false;
      audio.setAttribute("playsinline", "true");
      audioUrlRef.current = audio.src;
      audio.onended = () => {
        setSpeakingIndex(null); setVoiceState("idle"); URL.revokeObjectURL(audio.src); audioUrlRef.current = null;
        if (continueCall && callModeRef.current) window.setTimeout(() => { void startCallListening(); }, 250);
      };
      audioRef.current = audio; if (index >= 0) setSpeakingIndex(index); setVoiceState("speaking");
      try {
        await audio.play();
      } catch (playError) {
        // Mobile browsers may reject audible playback after the async TTS
        // request. Retry the already-unlocked element once if necessary.
        if (playError instanceof DOMException && playError.name === "NotAllowedError") {
          audio.muted = true;
          await audio.play();
          audio.muted = false;
        } else {
          throw playError;
        }
      }
      if (continueCall) void monitorBargeIn();
    } catch (err) {
      setSpeakingIndex(null); setVoiceState("idle"); setError(err instanceof Error ? err.message : "ଭଏସ୍ ତିଆରି ହୋଇପାରିଲା ନାହିଁ।");
      if (continueCall && callModeRef.current) window.setTimeout(() => { void startCallListening(); }, 700);
    }
  }
  async function speakMessage(text: string, index: number, language: LanguageCode = "od-IN") { if (speakingIndex === index) { stopPlayback(); return; } await playSpeech(text, index, false, language); }
  async function runVoiceTurn(text: string, history: Message[], mode: VoiceTurnMode = "manual") {
    const userMessage = text.trim(); if (!userMessage) throw new Error("କୌଣସି କଥା ଶୁଣାଯାଇନାହିଁ।");
    setError(""); setLoading(true); setMessages((current) => [...current, { role: "user", text: userMessage }]);
    if (mode === "call" && languageChoicePendingRef.current) {
      const preferredLanguage = detectPreferredLanguage(userMessage);
      setLoading(false);
      if (!preferredLanguage) {
        await playSpeech(CALL_LANGUAGE_RETRY, -1, true, "od-IN");
        return;
      }
      setCallLanguagePreference(preferredLanguage);
      const confirmation = preferredLanguage === "en-IN"
        ? "Great. I’ll continue in English. What would you like to know about Odisha?"
        : "ଠିକ୍ ଅଛି। ଆମେ ଓଡ଼ିଆରେ କଥା ହେବା। ଆପଣଙ୍କ ପ୍ରଶ୍ନ କୁହନ୍ତୁ।";
      await playSpeech(confirmation, -1, true, preferredLanguage);
      return;
    }
    try {
      const result = await sendMessage(userMessage, history);
      const assistantIndex = history.length + 1;
      if (mode === "call") { callLanguageRef.current = result.language; setCallLanguage(result.language); }
      setMessages((current) => [...current, { role: "assistant", text: result.reply, language: result.language }]);
      setLoading(false);
      await playSpeech(result.reply, assistantIndex, mode === "call", result.language);
    }
    catch (err) { setLoading(false); throw err; }
  }
  function formatCallTime(seconds: number) { return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`; }

  if (!isOpen) return <button className="launcher" type="button" onClick={() => setIsOpen(true)} aria-label="Odisha AI ଖୋଲନ୍ତୁ"><MessageCircle size={27} /><span>Odisha AI</span></button>;

  return <main className="widget-shell">
    <section className={`app-card ${isCallMode ? "call-card" : ""}`}>
      <header className="app-header">
        <div className="brand-mark"><Sparkles size={19} /></div><div className="brand-copy"><h1>{agentName}</h1><p><span className="online-dot" /> Online</p></div>
        {!isCallMode && <VoicePicker selected={selectedVoice} onChange={(voice) => setVoiceId(voice.id)} />}
        {!isCallMode && <button className="call-button" type="button" onClick={openCallPrompt}><Phone size={18} /> <span>Call</span></button>}
        {isCallMode && <div className="call-header-label"><Phone size={16} /> Voice call</div>}
        {!isCallMode && <button className="icon-button" type="button" onClick={resetConversation} aria-label="କଥୋପକଥନ ସଫା କରନ୍ତୁ"><RotateCcw size={18} /></button>}
        <button className="icon-button" type="button" onClick={() => { endCall(); setIsOpen(false); }} aria-label="Odisha AI ବନ୍ଦ କରନ୍ତୁ"><X size={19} /></button>
      </header>
      {isCallMode ? <div className="call-window">
        <div className="call-avatar"><Sparkles size={42} /></div><h2>{selectedVoice.name}</h2>
        <p className="call-subtitle">Odisha AI · {callLanguage === "en-IN" ? "English" : "ଓଡ଼ିଆ"} · {voiceState === "listening" ? "ଶୁଣୁଛି..." : voiceState === "processing" ? "ଚିନ୍ତା କରୁଛି..." : voiceState === "speaking" ? "କହୁଛି..." : "କଥା ହେବାକୁ ପ୍ରସ୍ତୁତ"}</p><span className="call-timer">{formatCallTime(callSeconds)}</span>
        <div className="call-controls"><button className={`round-control ${voiceState === "listening" ? "active" : ""}`} type="button" onClick={toggleRecording} disabled={loading || voiceState === "processing"} aria-label="ମାଇକ୍ରୋଫୋନ୍"><Mic size={22} /></button><button className="round-control end-call" type="button" onClick={endCall} aria-label="କଲ୍ ବନ୍ଦ କରନ୍ତୁ"><Phone size={22} /></button></div>
        {error && <div className="error call-error">{error}</div>}
      </div> : <>
        <div className="conversation">{messages.map((message, index) => <ChatMessage key={`${message.role}-${index}`} message={message} agentName={agentName} onSpeak={message.role === "assistant" ? () => speakMessage(message.text, index, message.language) : undefined} speaking={speakingIndex === index} />)}{loading && <div className="thinking">ଚିନ୍ତା କରୁଛି<span>.</span><span>.</span><span>.</span></div>}</div>
        {error && <div className="error">{error}</div>}
        <form className="composer" onSubmit={submit}><button type="button" className={`voice-button ${voiceState === "listening" ? "recording" : ""} ${voiceState === "speaking" ? "speaking" : ""}`} onClick={toggleRecording} disabled={loading || voiceState === "processing"} aria-label="କଥା କହନ୍ତୁ"><Mic size={21} /></button><input value={input} onChange={(event) => setInput(event.target.value)} placeholder={voiceState === "listening" ? "କହନ୍ତୁ..." : voiceState === "processing" ? "ଭଏସ୍ ବୁଝୁଛି..." : voiceState === "speaking" ? "ଉତ୍ତର ଶୁଣନ୍ତୁ..." : "ଆପଣଙ୍କ ପ୍ରଶ୍ନ ଲେଖନ୍ତୁ..."} disabled={loading || voiceState !== "idle"} /><button className="send-button" type="submit" disabled={!input.trim() || loading || voiceState !== "idle"} aria-label="ପଠାନ୍ତୁ"><ArrowUp size={20} /></button></form>
        <footer><span>{voiceState === "listening" ? "🎙 ଶୁଣୁଛି..." : voiceState === "processing" ? "⏳ ଚିନ୍ତା କରୁଛି..." : voiceState === "speaking" ? "🔊 କହୁଛି..." : `ସ୍ୱର: ${selectedVoice.name}`}</span><span>ଟେକ୍ସଟ୍ ମଧ୍ୟ ଲେଖିପାରିବେ</span></footer>
      </>}
    </section>
    {showCallPrompt && <div className="modal-backdrop" role="presentation"><div className="call-prompt" role="dialog" aria-modal="true" aria-labelledby="call-prompt-title"><div className="prompt-icon"><MessageCircle size={24} /><Phone size={24} /></div><h2 id="call-prompt-title">ଭଏସ୍ କଲ୍ ଆରମ୍ଭ କରିବେ?</h2><p>ଚାଟ୍ ଚାଲୁ ରହିବ ଏବଂ ଏକ ନୂଆ ଭଏସ୍ କଲ୍ ଆରମ୍ଭ ହେବ।</p><div className="prompt-actions"><button className="stay-button" type="button" onClick={() => setShowCallPrompt(false)}>ଚାଟ୍ ରେ ରୁହନ୍ତୁ</button><button className="switch-call-button" type="button" onClick={startCall}><Phone size={18} /> କଲ୍ ଆରମ୍ଭ କରନ୍ତୁ</button></div></div></div>}
  </main>;
}
