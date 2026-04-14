import { Module } from '@nestjs/common'
import { GoogleTrendsScraper } from './google-trends.scraper'

@Module({
  providers: [GoogleTrendsScraper],
  exports: [GoogleTrendsScraper],
})
export class ScrapersModule {}
