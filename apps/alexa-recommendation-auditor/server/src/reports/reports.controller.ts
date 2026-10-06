import { Controller, Get, Inject, NotFoundException, Param, Res } from "@nestjs/common";
import type { Response } from "express";
import { access } from "node:fs/promises";
import { resolve } from "node:path";
import { RunsService } from "../runs/runs.service";

@Controller()
export class ReportsController {
  constructor(@Inject(RunsService) private readonly runs: RunsService) {}

  @Get("api/v1/reports/:id")
  report(@Param("id") id: string) {
    return this.runs.report(id);
  }

  @Get("api/v1/artifacts/:runId/:name")
  async artifact(@Param("runId") runId: string, @Param("name") name: string, @Res() response: Response) {
    const path = await this.runs.artifactPath(runId, name);
    try {
      await access(path);
    } catch {
      throw new NotFoundException("截图不存在");
    }
    response.setHeader("Cache-Control", "private, max-age=3600");
    return response.sendFile(path);
  }

  @Get("reports/:id")
  async reportPage(@Param("id") id: string, @Res() response: Response) {
    const configured = process.env.REPORT_DIST_PATH || "../report/dist";
    const indexPath = resolve(process.cwd(), configured, "index.html");
    try {
      await access(indexPath);
      return response.sendFile(indexPath);
    } catch {
      return response.redirect(`http://127.0.0.1:4319/reports/${encodeURIComponent(id)}`);
    }
  }

  @Get("assets/:name")
  async reportAsset(@Param("name") name: string, @Res() response: Response) {
    if (!/^[A-Za-z0-9_.-]+$/.test(name)) throw new NotFoundException();
    const path = resolve(process.cwd(), process.env.REPORT_DIST_PATH || "../report/dist", "assets", name);
    try {
      await access(path);
      return response.sendFile(path);
    } catch {
      throw new NotFoundException();
    }
  }
}
