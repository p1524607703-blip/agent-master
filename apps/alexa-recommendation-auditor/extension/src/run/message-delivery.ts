export type ContentMessageFailure = {
  code: "content_receiver_missing" | "message_channel_closed" | "message_target_gone" | "content_message_failed";
  retryableBeforeDelivery: boolean;
  message: string;
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error || "Unknown Chrome message error");
}

export function classifyContentMessageFailure(error: unknown): ContentMessageFailure {
  const original = errorMessage(error);
  if (/receiving end does not exist|could not establish connection/i.test(original)) {
    return {
      code: "content_receiver_missing",
      retryableBeforeDelivery: true,
      message: `Amazon页面脚本尚未连接：${original}`
    };
  }
  if (/asynchronous response.*channel closed|message (?:port|channel) closed before a response|port closed before a response/i.test(original)) {
    return {
      code: "message_channel_closed",
      retryableBeforeDelivery: false,
      message: "Alexa页面在异步结果返回前发生跳转或被销毁；问题可能已经提交，为避免重复提问已禁止自动重发"
    };
  }
  if (/tab was closed|frame .* was removed|no tab with id/i.test(original)) {
    return {
      code: "message_target_gone",
      retryableBeforeDelivery: false,
      message: `Amazon测试页面已不存在：${original}`
    };
  }
  return {
    code: "content_message_failed",
    retryableBeforeDelivery: false,
    message: original
  };
}

export function contentMessageError(error: unknown): Error & { code: ContentMessageFailure["code"] } {
  const failure = classifyContentMessageFailure(error);
  return Object.assign(new Error(failure.message), { code: failure.code });
}
