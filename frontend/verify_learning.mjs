import { chromium } from 'playwright';

async function test() {
  const browser = await chromium.launch({ channel: 'msedge' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on('console', msg => console.log('[BROWSER]', msg.type(), msg.text()));
  page.on('pageerror', err => console.error('[PAGE ERROR]', err));
  
  await page.goto('http://192.168.100.11:3000');
  await page.locator('input[placeholder="用户名"]').fill('u_test_9435');
  await page.locator('input[placeholder*="密码"]').fill('Pass123456!');
  await page.locator('button:has-text("登录")').click();
  await page.waitForTimeout(1000);
  
  await page.locator('button:has-text("学习诊断")').click();
  await page.waitForTimeout(2000);
  const info = await page.evaluate(() => {
    const pageEl = document.querySelector('.learning-page');
    return {
      pageScrollWidth: pageEl.scrollWidth,
      pageOffsetWidth: pageEl.offsetWidth,
      statBoxes: Array.from(document.querySelectorAll('.stat-box')).map(el => ({
        text: el.innerText.split('\n')[0],
        width: el.getBoundingClientRect().width,
        height: el.getBoundingClientRect().height
      })),
      compCols: Array.from(document.querySelectorAll('.comp-col')).map(el => ({
        width: el.getBoundingClientRect().width,
        height: el.getBoundingClientRect().height
      }))
    };
  });
  console.log('LIVE NAS LEARNING VIEW MEASUREMENT:', JSON.stringify(info, null, 2));
  await page.screenshot({ path: 'docs/screenshots/adversarial_audit/08_desktop_learning_page.png' });
  await browser.close();
  console.log('DONE');
}

test();
