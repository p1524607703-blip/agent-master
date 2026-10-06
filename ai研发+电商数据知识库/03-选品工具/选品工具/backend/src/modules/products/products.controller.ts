import { Controller, Get, Post, Put, Delete, Param, Body, Query } from '@nestjs/common'
import { ProductsService } from './products.service'
import { Prisma } from '@prisma/client'

@Controller('products')
export class ProductsController {
  constructor(private readonly productsService: ProductsService) {}

  @Get()
  findAll(
    @Query('page') page?: string,
    @Query('pageSize') pageSize?: string,
    @Query('category') category?: string,
    @Query('status') status?: string,
  ) {
    return this.productsService.findAll({
      page: page ? +page : 1,
      pageSize: pageSize ? +pageSize : 20,
      category,
      status,
    })
  }

  @Get('stats')
  getDashboardStats() {
    return this.productsService.getDashboardStats()
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.productsService.findOne(id)
  }

  @Post()
  create(@Body() data: Prisma.ProductCreateInput) {
    return this.productsService.create(data)
  }

  @Put(':id')
  update(@Param('id') id: string, @Body() data: Prisma.ProductUpdateInput) {
    return this.productsService.update(id, data)
  }

  @Delete(':id')
  remove(@Param('id') id: string) {
    return this.productsService.remove(id)
  }
}
