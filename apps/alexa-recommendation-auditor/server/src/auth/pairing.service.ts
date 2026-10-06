import { Injectable, Logger } from "@nestjs/common";
import { randomBytes, randomInt, timingSafeEqual } from "node:crypto";

@Injectable()
export class PairingService {
  private readonly logger = new Logger(PairingService.name);
  private code = "";
  private readonly token = randomBytes(32).toString("hex");
  private readonly authenticationRequired: boolean;

  constructor() {
    const mode = String(process.env.LOCAL_AUTH_MODE || "auto").toLowerCase();
    if (!["auto", "disabled", "pairing"].includes(mode)) {
      throw new Error("LOCAL_AUTH_MODE must be one of: auto, disabled, pairing");
    }
    const isDevelopment = process.env.NODE_ENV === "development" || process.env.NODE_ENV === "test";
    this.authenticationRequired = mode === "pairing" || (mode === "auto" && !isDevelopment);
    if (this.authenticationRequired) {
      this.code = String(randomInt(100000, 999999));
      this.logger.log(`Chrome extension pairing code: ${this.code}`);
    } else {
      this.logger.log("Development mode: local pairing is disabled");
    }
  }

  pair(code: string): string | null {
    if (!this.authenticationRequired) return this.token;
    if (!this.code || code.length !== this.code.length) return null;
    const valid = timingSafeEqual(Buffer.from(code), Buffer.from(this.code));
    if (!valid) return null;
    this.code = "";
    return this.token;
  }

  verify(token: string): boolean {
    if (!this.authenticationRequired) return true;
    if (!token || token.length !== this.token.length) return false;
    return timingSafeEqual(Buffer.from(token), Buffer.from(this.token));
  }

  get pairingRequired() {
    return this.authenticationRequired && Boolean(this.code);
  }

  get authMode() {
    return this.authenticationRequired ? "pairing" : "disabled";
  }

  get authRequired() {
    return this.authenticationRequired;
  }
}
