import { describe, expect, it } from "vitest";
import { classifyContentMessageFailure, contentMessageError } from "../src/run/message-delivery";

describe("content message delivery classification", () => {
  it("retries only when Chrome proves no receiving listener existed", () => {
    expect(classifyContentMessageFailure(new Error("Could not establish connection. Receiving end does not exist."))).toMatchObject({
      code: "content_receiver_missing",
      retryableBeforeDelivery: true
    });
  });

  it("never retries a prompt after an asynchronous listener channel closes", () => {
    const failure = classifyContentMessageFailure(new Error(
      "A listener indicated an asynchronous response by returning true, but the message channel closed before a response was received"
    ));
    expect(failure).toMatchObject({ code: "message_channel_closed", retryableBeforeDelivery: false });
    expect(failure.message).toContain("避免重复提问");
  });

  it("preserves a machine-readable error code for the executor", () => {
    expect(contentMessageError(new Error("The tab was closed."))).toMatchObject({ code: "message_target_gone" });
  });
});
