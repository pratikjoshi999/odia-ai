export type LanguageCode = "od-IN" | "en-IN";
export type Message = { role: "user" | "assistant"; text: string; language?: LanguageCode };
export type ChatResponse = { reply: string; provider: string; request_id: string; language: LanguageCode };
export type AgentConfig = { id: string; name: string; tagline: string };
