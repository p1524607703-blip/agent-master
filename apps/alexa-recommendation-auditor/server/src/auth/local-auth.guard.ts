import { CanActivate, ExecutionContext, Inject, Injectable, UnauthorizedException } from "@nestjs/common";
import type { Request } from "express";
import { PairingService } from "./pairing.service";

@Injectable()
export class LocalAuthGuard implements CanActivate {
  constructor(@Inject(PairingService) private readonly pairing: PairingService) {}

  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest<Request>();
    const token = request.headers.authorization?.replace(/^Bearer\s+/i, "") || "";
    if (!this.pairing.verify(token)) throw new UnauthorizedException("Extension pairing token is missing or expired");
    return true;
  }
}
