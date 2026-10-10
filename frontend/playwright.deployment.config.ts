import {defineConfig} from '@playwright/test';

// Isolated local HTTP checks of the public-domain configuration; no DNS/TLS claim.
const publicConfig={NEXA_WORKSPACE_ORIGIN:'https://nexa-mk.voltwok.com/',
 NEXA_DEMO_AUTH_USERNAME:'TEST_ONLY_operator',NEXA_DEMO_AUTH_PASSWORD:'TEST_ONLY_private_demo_password'};
export default defineConfig({testDir:'./deployment-tests',workers:1,retries:0,timeout:30000,
 reporter:[['list'],['json',{outputFile:'../.local/deployment-browser-results.json'}]],
 webServer:[
  {command:'npm run start -- --hostname 127.0.0.1 --port 3011',port:3011,reuseExistingServer:false,
   env:{...publicConfig,NEXA_WORKSPACE_MODE:'private_demo'},timeout:30000},
  {command:'npm run start -- --hostname 127.0.0.1 --port 3012',port:3012,reuseExistingServer:false,
   env:{...publicConfig,NEXA_WORKSPACE_MODE:'',NEXA_DEMO_AUTH_PASSWORD:''},timeout:30000},
 ]});
