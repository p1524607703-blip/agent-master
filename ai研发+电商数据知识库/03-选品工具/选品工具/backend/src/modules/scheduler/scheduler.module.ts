import { Module } from '@nestjs/common'
import { SchedulerService } from './scheduler.service'
import { AgentsModule } from '../agents/agents.module'

@Module({
  imports: [AgentsModule],
  providers: [SchedulerService],
})
export class SchedulerModule {}
