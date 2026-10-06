import { Module } from '@nestjs/common'
import { ConfigModule } from '@nestjs/config'
import { BullModule } from '@nestjs/bull'
import { ScheduleModule } from '@nestjs/schedule'
import { ProductsModule } from './modules/products/products.module'
import { TrendsModule } from './modules/trends/trends.module'
import { AnalysisModule } from './modules/analysis/analysis.module'
import { AgentsModule } from './modules/agents/agents.module'
import { AlertsModule } from './modules/alerts/alerts.module'
import { PrismaModule } from './prisma/prisma.module'
import { ScrapersModule } from './scrapers/scrapers.module'
import { SchedulerModule } from './modules/scheduler/scheduler.module'

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    ScheduleModule.forRoot(),
    ...(process.env.REDIS_HOST ? [
      BullModule.forRoot({
        redis: {
          host: process.env.REDIS_HOST || 'localhost',
          port: parseInt(process.env.REDIS_PORT || '6379'),
        },
      }),
    ] : []),
    PrismaModule,
    ProductsModule,
    TrendsModule,
    AnalysisModule,
    AgentsModule,
    AlertsModule,
    ScrapersModule,
    SchedulerModule,
  ],
})
export class AppModule {}
