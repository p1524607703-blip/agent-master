import "reflect-metadata";
import { Logger, ValidationPipe } from "@nestjs/common";
import { NestFactory } from "@nestjs/core";
import cookieParser from "cookie-parser";
import dotenv from "dotenv";
import { json } from "express";
import helmet from "helmet";
import { resolve } from "node:path";
import { AppModule } from "./app.module";

dotenv.config({ path: resolve(process.cwd(), "../.env") });

async function bootstrap() {
  const app = await NestFactory.create(AppModule, { bodyParser: false });
  app.use(json({ limit: "12mb" }));
  app.use(cookieParser());
  app.use(helmet({ contentSecurityPolicy: false, crossOriginResourcePolicy: { policy: "cross-origin" } }));
  app.enableCors({
    origin(origin: string | undefined, callback: (error: Error | null, allow?: boolean) => void) {
      if (!origin || origin.startsWith("chrome-extension://") || /^http:\/\/127\.0\.0\.1:\d+$/.test(origin) || /^http:\/\/localhost:\d+$/.test(origin)) return callback(null, true);
      return callback(new Error("Origin is not permitted by the local auditor"), false);
    },
    methods: ["GET", "POST", "PATCH", "OPTIONS"],
    allowedHeaders: ["Content-Type", "Authorization"]
  });
  app.useGlobalPipes(new ValidationPipe({ transform: true, whitelist: false }));
  app.enableShutdownHooks();
  const port = Number(process.env.PORT || 4318);
  await app.listen(port, "127.0.0.1");
  Logger.log(`Local auditor listening on http://127.0.0.1:${port}`, "Bootstrap");
}

bootstrap().catch((error) => {
  Logger.error(error instanceof Error ? error.stack : String(error), "Bootstrap");
  process.exitCode = 1;
});
