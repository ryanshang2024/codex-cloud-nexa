import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',workers:1,retries:0,timeout:60000,
 use:{baseURL:'http://127.0.0.1:3000',browserName:'chromium',launchOptions:{executablePath:'/usr/bin/chromium',args:['--no-sandbox']},trace:'retain-on-failure'},
 reporter:[['list'],['json',{outputFile:'../.local/browser-results.json'}]]});
