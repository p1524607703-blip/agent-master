import { Body, Controller, Get, Inject, Post, UnauthorizedException } from "@nestjs/common";
import { PairingService } from "./pairing.service";
import { APP_VERSION, getScoringStandards } from "@alexa-auditor/contracts";
import { DeepSeekService } from "../deepseek/deepseek.service";

@Controller("api/v1")
export class AuthController {
  constructor(
    @Inject(PairingService) private readonly pairing: PairingService,
    @Inject(DeepSeekService) private readonly model: DeepSeekService
  ) {}

  @Get("health")
  async health() {
    return {
      ok: true,
      service: "alexa-recommendation-auditor",
      authRequired: this.pairing.authRequired,
      pairingRequired: this.pairing.pairingRequired,
      authMode: this.pairing.authMode,
      version: APP_VERSION,
      modelTransport: await this.model.health()
    };
  }

  @Get("scoring-standards")
  scoringStandards() {
    return getScoringStandards();
  }

  @Post("pair")
  pair(@Body() body: { code?: string }) {
    const token = this.pairing.pair(String(body.code || ""));
    if (!token) throw new UnauthorizedException("配对码无效或已经使用");
    return { token };
  }
}
