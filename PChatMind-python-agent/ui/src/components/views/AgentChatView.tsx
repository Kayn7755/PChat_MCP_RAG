import React, { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { message as antdMessage } from "antd";
import AgentChatHistory from "./agentChatView/AgentChatHistory.tsx";
import AgentChatInput from "./agentChatView/AgentChatInput.tsx";
import {
  createChatMessage,
  createChatSession,
  getChatMessagesBySessionId,
  getChatSession,
} from "../../api/api.ts";
import { useAgents } from "../../hooks/useAgents.ts";
import { useChatSessions } from "../../hooks/useChatSessions.ts";
import EmptyAgentChatView from "./agentChatView/EmptyAgentChatView.tsx";
import type { ChatMessageVO, SseMessage, SseMessageType } from "../../types";

type ChatLocationState = {
  init?: boolean;
  initMessage?: string;
};

const AgentChatView: React.FC = () => {
  const { chatSessionId } = useParams<{ chatSessionId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state as ChatLocationState | null) ?? undefined;
  const [loading, setLoading] = useState(false);
  const { agents } = useAgents();
  const { refreshChatSessions } = useChatSessions();

  const [messages, setMessages] = useState<ChatMessageVO[]>([]);

  const addMessage = (message: ChatMessageVO) => {
    setMessages((prevMessages) => [...prevMessages, message]);
  };

  const [agentId, setAgentId] = useState<string>("");
  const sseReadyRef = useRef(false);
  const initSentRef = useRef(false);

  const getChatMessages = useCallback(async () => {
    if (!chatSessionId) {
      return;
    }
    const resp = await getChatMessagesBySessionId(chatSessionId);
    setMessages(resp.chatMessages);

    const fetchData = async () => {
      const resp = await getChatSession(chatSessionId);
      setAgentId(resp.chatSession.agentId);
    };
    fetchData().then();
  }, [chatSessionId]);

  const prevSessionRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!chatSessionId) {
      return;
    }
    if (prevSessionRef.current !== chatSessionId) {
      prevSessionRef.current = chatSessionId;
      initSentRef.current = false;
      sseReadyRef.current = false;
    }
    getChatMessages().then();
  }, [chatSessionId, getChatMessages]);

  const handleSendMessage = async (value: string | { text: string }) => {
    const message = typeof value === "string" ? value : value.text;

    console.log(message);

    if (!message || !message.trim()) return;

    // 如果没有 chatSessionId，创建新会话
    if (!chatSessionId) {
      if (!agentId) {
        antdMessage.warning("请先创建一个智能体助手");
        return;
      }
      setLoading(true);
      try {
        const response = await createChatSession({
          agentId: agentId,
          title: message.slice(0, 20),
        });
        await refreshChatSessions();
        navigate(`/chat/${response.chatSessionId}`, {
          replace: true,
          state: {
            init: true,
            initMessage: message,
          },
        });
      } catch (error) {
        console.error("创建聊天会话失败:", error);
        antdMessage.error("创建聊天会话失败，请重试");
      } finally {
        setLoading(false);
      }
    } else {
      if (!agentId) {
        antdMessage.warning("会话智能体未就绪，请稍后重试");
        return;
      }
      await createChatMessage({
        agentId,
        sessionId: chatSessionId,
        role: "user",
        content: message,
      });
      await getChatMessages();
    }
  };

  const [displayAgentStatus, setDisplayAgentStatus] = useState<boolean>(false);
  const [agentStatusText, setAgentStatusText] = useState("");
  const [agentStatusType, setAgentStatusType] = useState<
    SseMessageType | undefined
  >(undefined);

  useEffect(() => {
    if (!chatSessionId) {
      return;
    }
    const sseBase = (import.meta.env.VITE_SSE_BASE ?? "").replace(/\/$/, "");
    const ssePath = `/sse/connect/${chatSessionId}`;
    const sseUrl = sseBase ? `${sseBase}${ssePath}` : ssePath;
    const es = new EventSource(sseUrl);
    es.onerror = (error) => {
      console.error("SSE error:", error);
    };

    es.addEventListener("init", () => {
      sseReadyRef.current = true;
    });

    es.addEventListener("message", (event) => {
      try {
        const message = JSON.parse(event.data) as SseMessage;
        if (message.type === "AI_GENERATED_CONTENT") {
          if (message.payload?.message) {
            addMessage(message.payload.message);
          }
        } else if (message.type === "AI_PLANNING") {
          setDisplayAgentStatus(true);
          setAgentStatusText(message.payload.statusText);
          setAgentStatusType("AI_PLANNING");
        } else if (message.type === "AI_THINKING") {
          setDisplayAgentStatus(true);
          setAgentStatusText(message.payload.statusText);
          setAgentStatusType("AI_THINKING");
        } else if (message.type === "AI_EXECUTING") {
          setDisplayAgentStatus(true);
          setAgentStatusText(message.payload.statusText);
          setAgentStatusType("AI_EXECUTING");
        } else if (message.type === "AI_DONE") {
          setDisplayAgentStatus(false);
          const doneText = message.payload?.statusText ?? "";
          setAgentStatusText("");
          setAgentStatusType(undefined);
          if (doneText.includes("失败")) {
            antdMessage.error(doneText);
          }
          getChatMessages().then();
        } else {
          console.warn("Unknown SSE message type:", message.type);
        }
      } catch (e) {
        console.error("SSE message parse/handle failed:", e);
      }
    });

    return () => {
      console.log("Closing SSE connection.");
      sseReadyRef.current = false;
      es.close();
    };
  }, [chatSessionId, getChatMessages]);

  // 空会话页跳转过来：等 agentId + SSE 就绪后再发首条消息，避免推送丢失
  useEffect(() => {
    if (!chatSessionId || !state?.init || !state?.initMessage) return;
    if (!agentId || initSentRef.current) return;

    let cancelled = false;
    const trySend = async () => {
      // 最多等 ~2s 让 EventSource init 事件到达
      for (let i = 0; i < 20 && !sseReadyRef.current; i++) {
        await new Promise((r) => setTimeout(r, 100));
        if (cancelled) return;
      }
      if (cancelled || initSentRef.current) return;
      initSentRef.current = true;
      const text = state.initMessage ?? "";
      // 先清 state，避免 Strict Mode / 重渲染再次触发
      navigate(location.pathname, { replace: true, state: {} });
      try {
        await createChatMessage({
          agentId,
          sessionId: chatSessionId,
          role: "user",
          content: text,
        });
        await getChatMessages();
      } catch (e) {
        initSentRef.current = false;
        console.error("发送首条消息失败:", e);
        antdMessage.error("发送消息失败，请重试");
      }
    };
    trySend();
    return () => {
      cancelled = true;
    };
  }, [
    chatSessionId,
    agentId,
    state?.init,
    state?.initMessage,
    getChatMessages,
    navigate,
    location.pathname,
  ]);

  // 如果没有 chatSessionId，显示提示界面
  if (!chatSessionId) {
    return (
      <EmptyAgentChatView
        agents={agents}
        loading={loading}
        handleSendMessage={handleSendMessage}
      />
    );
  }

  // 如果有 chatSessionId，显示正常的聊天界面
  return (
    <div className="flex flex-col h-full">
      <AgentChatHistory
        messages={messages}
        displayAgentStatus={displayAgentStatus}
        agentStatusText={agentStatusText}
        agentStatusType={agentStatusType}
      />
      <div className="border-t border-gray-200 p-4 bg-white">
        <AgentChatInput onSend={handleSendMessage} />
      </div>
    </div>
  );
};

export default AgentChatView;
