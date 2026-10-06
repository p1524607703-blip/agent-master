import { Module } from "@nestjs/common";
import { AuthController } from "./auth/auth.controller";
import { LocalAuthGuard } from "./auth/local-auth.guard";
import { PairingService } from "./auth/pairing.service";
import { DeepSeekService } from "./deepseek/deepseek.service";
import { HermesTransportService } from "./hermes/hermes-transport.service";
import { PrismaService } from "./prisma.service";
import { ProductsController } from "./products/products.controller";
import { ProductsService } from "./products/products.service";
import { ReportsController } from "./reports/reports.controller";
import { RunEventsService } from "./runs/run-events.service";
import { RunsController } from "./runs/runs.controller";
import { RunsService } from "./runs/runs.service";

@Module({
  controllers: [AuthController, ProductsController, RunsController, ReportsController],
  providers: [PrismaService, PairingService, LocalAuthGuard, HermesTransportService, DeepSeekService, ProductsService, RunsService, RunEventsService]
})
export class AppModule {}
