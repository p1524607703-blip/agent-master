import { Controller, Get, Post, Patch, Param, Query, Body } from '@nestjs/common'
import { AlertsService } from './alerts.service'
import { Prisma } from '@prisma/client'

@Controller('alerts')
export class AlertsController {
  constructor(private readonly alertsService: AlertsService) {}

  @Get()
  findAll(
    @Query('unreadOnly') unreadOnly?: string,
    @Query('productId') productId?: string,
  ) {
    return this.alertsService.findAll({
      unreadOnly: unreadOnly === 'true',
      productId,
    })
  }

  @Get('unread-count')
  getUnreadCount() {
    return this.alertsService.getUnreadCount()
  }

  @Patch(':id/read')
  markRead(@Param('id') id: string) {
    return this.alertsService.markRead(id)
  }

  @Patch('read-all')
  markAllRead() {
    return this.alertsService.markAllRead()
  }

  @Post()
  create(@Body() data: Prisma.AlertCreateInput) {
    return this.alertsService.create(data)
  }
}
