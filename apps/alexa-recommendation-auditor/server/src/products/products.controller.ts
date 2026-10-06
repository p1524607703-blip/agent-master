import { Body, Controller, Get, Inject, NotFoundException, Param, Post, UseGuards } from "@nestjs/common";
import type { ProductSnapshot } from "@alexa-auditor/contracts";
import { LocalAuthGuard } from "../auth/local-auth.guard";
import { ProductsService } from "./products.service";

@Controller("api/v1/product-snapshots")
@UseGuards(LocalAuthGuard)
export class ProductsController {
  constructor(@Inject(ProductsService) private readonly products: ProductsService) {}

  @Post()
  create(@Body() body: Partial<ProductSnapshot>) {
    return this.products.create(body);
  }

  @Get(":id")
  async get(@Param("id") id: string) {
    const product = await this.products.get(id);
    if (!product) throw new NotFoundException("商品快照不存在");
    return product;
  }
}
