import { Injectable, Logger, Optional } from '@nestjs/common'
import { InjectQueue } from '@nestjs/bull'
import { Queue } from 'bull'
import { PrismaService } from '../../prisma/prisma.service'

export type AgentTaskType = 'scan' | 'ai_analysis' | 'alert_check' | 'report'

@Injectable()
export class AgentsService {
  private readonly logger = new Logger(AgentsService.name)

  constructor(
    private prisma: PrismaService,
    @Optional() @InjectQueue('agent-tasks') private agentQueue?: Queue,
  ) {}

  async findAll(status?: string) {
    return this.prisma.agentTask.findMany({
      where: status ? { status } : {},
      orderBy: { createdAt: 'desc' },
      take: 50,
    })
  }

  async findOne(id: string) {
    return this.prisma.agentTask.findUniqueOrThrow({ where: { id } })
  }

  async dispatch(type: AgentTaskType, name: string, payload?: object) {
    const task = await this.prisma.agentTask.create({
      data: { name, type, status: 'pending' },
    })
    if (this.agentQueue) await this.agentQueue.add(type, { taskId: task.id, payload }, { attempts: 3 })
    this.logger.log(`Dispatched task ${task.id}: ${type}`)
    return task
  }

  async updateProgress(id: string, progress: number, status?: string) {
    return this.prisma.agentTask.update({
      where: { id },
      data: { progress, ...(status ? { status } : {}) },
    })
  }

  async complete(id: string, result: object) {
    return this.prisma.agentTask.update({
      where: { id },
      data: { status: 'completed', progress: 100, result, completedAt: new Date() },
    })
  }

  async fail(id: string, error: string) {
    return this.prisma.agentTask.update({
      where: { id },
      data: { status: 'failed', error },
    })
  }

  async getStats() {
    const [pending, running, completed, failed] = await Promise.all([
      this.prisma.agentTask.count({ where: { status: 'pending' } }),
      this.prisma.agentTask.count({ where: { status: 'running' } }),
      this.prisma.agentTask.count({ where: { status: 'completed' } }),
      this.prisma.agentTask.count({ where: { status: 'failed' } }),
    ])
    return { pending, running, completed, failed }
  }
}
