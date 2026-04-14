import { Controller, Get, Post, Param, Query, Body } from '@nestjs/common'
import { AgentsService, AgentTaskType } from './agents.service'

@Controller('agents')
export class AgentsController {
  constructor(private readonly agentsService: AgentsService) {}

  @Get()
  findAll(@Query('status') status?: string) {
    return this.agentsService.findAll(status)
  }

  @Get('stats')
  getStats() {
    return this.agentsService.getStats()
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.agentsService.findOne(id)
  }

  @Post('dispatch')
  dispatch(@Body() body: { type: AgentTaskType; name: string; payload?: object }) {
    return this.agentsService.dispatch(body.type, body.name, body.payload)
  }
}
