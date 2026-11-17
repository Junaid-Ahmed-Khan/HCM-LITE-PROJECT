
import { useState } from "react";
import api from "../api/axios";
import "./AIAssistant.css";

export default function AIAssistant() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I'm your HCM Lite AI Assistant. Ask me about attendance, leave requests, payroll, or employee summaries available to your account.",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || loading) return;

    setError("");
    setQuestion("");
    setMessages((previous) => [
      ...previous,
      { role: "user", content: trimmedQuestion },
    ]);
    setLoading(true);

    try {
      const response = await api.post("/ai/ask", {
        question: trimmedQuestion,
      });

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content:
            response.data?.answer ||
            "The assistant returned an empty response.",
        },
      ]);
    } catch (err) {
      const status = err.response?.status;

      let message = "Unable to contact the AI assistant. Please try again.";

      if (status === 401) {
        message = "Your session may have expired. Please sign in again.";
      } else if (status === 403) {
        message = "Your account is not permitted to use the AI assistant.";
      } else if (status === 502) {
        message =
          "The AI service could not generate a response. Please try again.";
      } else if (!err.response) {
        message =
          "Cannot connect to the backend. Check that the backend server is running.";
      } else if (status === 422) {
        message = "Please enter a valid question.";
      }

      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="ai-assistant-page">
      <div className="ai-assistant-heading">
        <div>
          <h2>AI Assistant</h2>
          <p>
            Ask questions about HCM information available to your account.
          </p>
        </div>
        <span className="ai-status">AI Assistant</span>
      </div>

      <div
        className="ai-chat-window"
        aria-live="polite"
        aria-label="AI conversation"
      >
        {messages.map((message, index) => (
          <div
            key={`${index}-${message.role}`}
            className={`ai-message ai-message-${message.role}`}
          >
            <span className="ai-message-label">
              {message.role === "user" ? "You" : "HCM AI"}
            </span>
            <p>{message.content}</p>
          </div>
        ))}

        {loading && (
          <div className="ai-message ai-message-assistant">
            <span className="ai-message-label">HCM AI</span>
            <p>Thinking...</p>
          </div>
        )}
      </div>

      {error && (
        <p className="ai-error" role="alert">
          {error}
        </p>
      )}

      <form className="ai-chat-form" onSubmit={handleSubmit}>
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about attendance, payroll, or leave..."
          maxLength={2000}
          rows={2}
          disabled={loading}
          aria-label="Your question"
        />

        <button
          type="submit"
          disabled={loading || !question.trim()}
        >
          {loading ? "Sending..." : "Send"}
        </button>
      </form>

      <p className="ai-disclaimer">
        Answers depend on the information and permissions available to your
        account. Verify important HR decisions against official records.
      </p>
    </section>
  );
}
