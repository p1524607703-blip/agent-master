import { Body, Controller, Get, Inject, MessageEvent, Param, Patch, Post, Sse, UseGuards } from "@nestjs/common";
import type { ApproveQuestionPlanRequest, ConversationTurn, CreateRunRequest, UpdatePromptCaseRequest } from "@alexa-auditor/contracts";
import type { Observable } from "rxjs";
import { LocalAuthGuard } from "../auth/local-auth.guard";
import { RunEventsService } from "./run-events.service";
import { RunsService } from "./runs.service";

@Controller("api/v1/runs")
@UseGuards(LocalAuthGuard)
export class RunsController {
  constructor(
    @Inject(RunsService) private readonly runs: RunsService,
    @Inject(RunEventsService) private readonly events: RunEventsService
  ) {}

  @Post()
  create(@Body() body: CreateRunRequest) {
    return this.runs.create(body);
  }

  @Get("scoring-standards")
  scoringStandards() {
    return this.runs.scoringStandards();
  }

  @Get(":id")
  get(@Param("id") id: string) {
    return this.runs.get(id);
  }

  @Get(":id/audit")
  audit(@Param("id") id: string) {
    return this.runs.audit(id);
  }

  @Patch(":id/prompts/:promptCaseId")
  updatePrompt(
    @Param("id") id: string,
    @Param("promptCaseId") promptCaseId: string,
    @Body() body: UpdatePromptCaseRequest
  ) {
    return this.runs.updatePrompt(id, promptCaseId, body);
  }

  @Post(":id/question-plan/approve")
  approveQuestionPlan(@Param("id") id: string, @Body() body: ApproveQuestionPlanRequest) {
    return this.runs.approveQuestionPlan(id, body);
  }

  @Post(":id/start")
  start(@Param("id") id: string) {
    return this.runs.start(id);
  }

  @Post(":id/turns")
  addTurn(@Param("id") id: string, @Body() body: ConversationTurn) {
    return this.runs.addTurn(id, body);
  }

  @Post(":id/stop")
  stop(@Param("id") id: string, @Body() body: { reason?: string }) {
    return this.runs.stop(id, body.reason || "user_requested");
  }

  @Sse(":id/events")
  stream(@Param("id") id: string): Observable<MessageEvent> {
    return this.events.stream(id);
  }
}
