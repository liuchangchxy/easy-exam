import { chromium } from 'playwright';
import path from 'path';

async function testRemote() {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true
  });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();

  console.log('Visiting remote http://192.168.x.x:3000 ...');
  await page.goto('http://192.168.x.x:3000', { waitUntil: 'networkidle' });
  await page.screenshot({ path: 'screenshots/mobile/remote_login.png' });

  // Login as admin
  await page.fill('input[placeholder="用户名"]', 'admin');
  await page.fill('input[placeholder="密码（至少 8 位）"]', 'REDACTED_ADMIN_PASSWORD');
  await page.click('button:has-text("登录")');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'screenshots/mobile/remote_home.png' });

  // Click start practice
  await page.click('button:has-text("开始刷题")');
  await page.waitForSelector('.question-card');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'screenshots/mobile/remote_practice.png' });

  const headerH = await page.evaluate(() => document.querySelector('.compact-header')?.clientHeight || document.querySelector('.page-header')?.clientHeight);
  const hasSkipBtn = await page.evaluate(() => !!document.querySelector('.btn-skip-unanswered') || !!document.querySelector('.btn-sheet-trigger-pill'));

  console.log('Remote Practice Header Height:', headerH);
  console.log('Remote Has Skip/Sheet buttons:', hasSkipBtn);

  await browser.close();
}

testRemote().catch(console.error);
