import { Volume2 } from "lucide-react";
import type { Message } from "../types/chat";

export function ChatMessage({ message, agentName = "Odisha AI", onSpeak, speaking }: { message: Message; agentName?: string; onSpeak?: () => void; speaking?: boolean }) {
  return <div className={`message-row ${message.role}`}><div className="message"><span className="message-label">{message.role === "user" ? "ଆପଣ" : agentName}</span><p>{message.text}</p>{message.role === "assistant" && onSpeak && <button className={`speak-button ${speaking ? "speaking" : ""}`} onClick={onSpeak} type="button" aria-label={speaking ? "ଅଡିଓ ବନ୍ଦ କରନ୍ତୁ" : "ଉତ୍ତର ଶୁଣନ୍ତୁ"}><Volume2 size={15} /> {speaking ? "ବନ୍ଦ" : "ଶୁଣନ୍ତୁ"}</button>}</div></div>;
}
