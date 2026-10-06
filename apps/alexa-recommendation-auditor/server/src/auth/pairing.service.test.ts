import { afterEach, describe, expect, it } from "vitest";
import { PairingService } from "./pairing.service";

const originalNodeEnv = process.env.NODE_ENV;
const originalAuthMode = process.env.LOCAL_AUTH_MODE;

afterEach(() => {
  if (originalNodeEnv === undefined) delete process.env.NODE_ENV;
  else process.env.NODE_ENV = originalNodeEnv;
  if (originalAuthMode === undefined) delete process.env.LOCAL_AUTH_MODE;
  else process.env.LOCAL_AUTH_MODE = originalAuthMode;
});

describe("PairingService authentication modes", () => {
  it("disables pairing by default outside production", () => {
    process.env.NODE_ENV = "development";
    delete process.env.LOCAL_AUTH_MODE;
    const service = new PairingService();
    expect(service.authMode).toBe("disabled");
    expect(service.pairingRequired).toBe(false);
    expect(service.verify("")).toBe(true);
  });

  it("requires pairing in production auto mode", () => {
    process.env.NODE_ENV = "production";
    process.env.LOCAL_AUTH_MODE = "auto";
    const service = new PairingService();
    expect(service.authMode).toBe("pairing");
    expect(service.pairingRequired).toBe(true);
    expect(service.verify("")).toBe(false);
  });

  it("fails closed when the runtime environment is unspecified", () => {
    delete process.env.NODE_ENV;
    process.env.LOCAL_AUTH_MODE = "auto";
    expect(new PairingService().authRequired).toBe(true);
  });

  it("honors explicit development overrides", () => {
    process.env.NODE_ENV = "development";
    process.env.LOCAL_AUTH_MODE = "pairing";
    expect(new PairingService().authMode).toBe("pairing");

    process.env.NODE_ENV = "production";
    process.env.LOCAL_AUTH_MODE = "disabled";
    expect(new PairingService().authMode).toBe("disabled");
  });

  it("rejects an invalid auth mode", () => {
    process.env.LOCAL_AUTH_MODE = "anything";
    expect(() => new PairingService()).toThrow(/LOCAL_AUTH_MODE/);
  });
});
