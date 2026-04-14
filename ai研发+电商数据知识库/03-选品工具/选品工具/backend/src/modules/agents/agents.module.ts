import { Module } from '@nestjs/common'
import { BullModule } from '@nestjs/bull'
import { AgentsController } from './agents.controller'
import { AgentsService } from './agents.service'
import { AgentProcessor } from './agent.processor'
import { ScrapersModule } from '../../scrapers/scrapers.module'

@Module({
  imports: [
    ...(process.env.REDIS_HOST ? [BullModule.registerQueue({ name: 'agent-tasks' })] : []),
    ScrapersModule,
  ],
  controllers: [AgentsController],
  providers: [AgentsService, AgentProcessor],
  exports: [AgentsService],
})
export class AgentsModule {}
