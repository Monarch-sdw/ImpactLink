import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',workers:1,timeout:60000,use:{baseURL:process.env.TEST_URL||'http://localhost:3017',headless:true,channel:'chrome'},reporter:'list'});
