import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import ChatView from "./ChatView";

vi.mock("../api", () => ({
  api: {
    messages: vi.fn(),
    chat: vi.fn(),
  },
}));

const mockApi = vi.mocked(api);

const ragResponse = {
  session_id: "s1",
  message_id: 2,
  role: "assistant",
  content: "The deadline is Friday [1].",
  mode: "rag",
  grounded: true,
  sources: [{
    chunk_id: "c1",
    document_id: "d1",
    document_name: "plan.txt",
    rel_path: "docs/plan.txt",
    page: 3,
    sheet: null,
    slide: null,
    snippet: "The deadline is Friday.",
    score: 0.9,
  }],
};

describe("ChatView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.messages.mockResolvedValue([]);
  });

  it("sends a message and shows grounded sources via the info button", async () => {
    mockApi.chat.mockResolvedValue(ragResponse);
    const onSession = vi.fn();
    render(<ChatView sessionId={null} onSessionChange={onSession} />);

    await userEvent.type(
      screen.getByPlaceholderText("Type a message…"), "when is the deadline?");
    await userEvent.click(screen.getByText("Send"));

    expect(await screen.findByText("The deadline is Friday [1]."))
      .toBeInTheDocument();
    expect(onSession).toHaveBeenCalledWith("s1");

    await userEvent.click(screen.getByLabelText("answer details"));
    const panel = await screen.findByTestId("sources-panel");
    expect(panel).toHaveTextContent("plan.txt");
    expect(panel).toHaveTextContent("p. 3");
  });

  it("marks answers without evidence", async () => {
    mockApi.chat.mockResolvedValue({
      ...ragResponse, mode: "rag_no_evidence",
      sources: [], grounded: false,
      content: "The documents do not contain an answer.",
    });
    render(<ChatView sessionId={null} onSessionChange={vi.fn()} />);
    await userEvent.type(screen.getByPlaceholderText("Type a message…"), "q");
    await userEvent.click(screen.getByText("Send"));
    expect(await screen.findByText("no evidence in documents"))
      .toBeInTheDocument();
  });

  it("keeps the failed message out of history on error", async () => {
    mockApi.chat.mockRejectedValue(new Error("Ollama down"));
    render(<ChatView sessionId={null} onSessionChange={vi.fn()} />);
    await userEvent.type(screen.getByPlaceholderText("Type a message…"), "hi");
    await userEvent.click(screen.getByText("Send"));
    await waitFor(() =>
      expect(screen.getByText("Ollama down")).toBeInTheDocument());
    expect(screen.queryByText("hi")).not.toBeInTheDocument();
  });
});
