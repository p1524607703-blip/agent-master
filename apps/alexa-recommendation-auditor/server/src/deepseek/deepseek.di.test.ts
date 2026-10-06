import { Module } from "@nestjs/common";
import { NestFactory } from "@nestjs/core";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HermesTransportService } from "../hermes/hermes-transport.service";
import { DeepSeekService } from "./deepseek.service";

@Module({ providers: [HermesTransportService, DeepSeekService] })
class ModelTransportTestModule {}

describe("DeepSeekService dependency injection", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("resolves the Hermes transport in the same metadata-light runtime used by tsx", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642");
    const app = await NestFactory.createApplicationContext(ModelTransportTestModule, { logger: false });
    try {
      expect(app.get(DeepSeekService).transportStatus).toMatchObject({
        mode: "hermes_only",
        configured: true,
        endpoint: "http://127.0.0.1:8642/v1/chat/completions"
      });
    } finally {
      await app.close();
    }
  });
});
