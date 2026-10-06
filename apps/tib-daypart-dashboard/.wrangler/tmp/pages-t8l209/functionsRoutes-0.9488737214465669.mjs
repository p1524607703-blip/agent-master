import { onRequest as __api_hermes___path___ts_onRequest } from "/Users/panjinlong/Documents/agent-master/apps/tib-daypart-dashboard/functions/api/hermes/[[path]].ts"

export const routes = [
    {
      routePath: "/api/hermes/:path*",
      mountPath: "/api/hermes",
      method: "",
      middlewares: [],
      modules: [__api_hermes___path___ts_onRequest],
    },
  ]