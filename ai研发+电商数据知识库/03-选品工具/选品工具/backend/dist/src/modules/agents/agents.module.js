"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AgentsModule = void 0;
const common_1 = require("@nestjs/common");
const bull_1 = require("@nestjs/bull");
const agents_controller_1 = require("./agents.controller");
const agents_service_1 = require("./agents.service");
const agent_processor_1 = require("./agent.processor");
const scrapers_module_1 = require("../../scrapers/scrapers.module");
let AgentsModule = class AgentsModule {
};
exports.AgentsModule = AgentsModule;
exports.AgentsModule = AgentsModule = __decorate([
    (0, common_1.Module)({
        imports: [
            ...(process.env.REDIS_HOST ? [bull_1.BullModule.registerQueue({ name: 'agent-tasks' })] : []),
            scrapers_module_1.ScrapersModule,
        ],
        controllers: [agents_controller_1.AgentsController],
        providers: [agents_service_1.AgentsService, agent_processor_1.AgentProcessor],
        exports: [agents_service_1.AgentsService],
    })
], AgentsModule);
//# sourceMappingURL=agents.module.js.map