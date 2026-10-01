import { chromium } from 'playwright';

async function run() {
  const browser = await chromium.launch({ channel: 'msedge' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto('http://192.168.100.11:3000', { waitUntil: 'networkidle' });

  // Login
  await page.locator('input[placeholder="用户名"]').fill('u_test_9435');
  await page.locator('input[placeholder*="密码"]').fill('Pass123456!');
  await page.locator('button:has-text("登录")').click();
  await page.waitForSelector('.page-header', { timeout: 10000 });

  // Click on a bank to enter practice if any exists
  const bankCard = await page.$('.bank-card');
  if (bankCard) {
    const practiceBtn = await bankCard.$('button:has-text("开始刷题")');
    if (practiceBtn) {
      await practiceBtn.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'frontend/practice_live_verified.png' });
      
      const headerBox = await page.$eval('.compact-header', el => {
        const s = window.getComputedStyle(el);
        return { display: s.display, flexWrap: s.flexWrap, height: el.offsetHeight, width: el.offsetWidth };
      });
      const actionsBox = await page.$eval('.header-actions', el => {
        const s = window.getComputedStyle(el);
        return { display: s.display, flexDirection: s.flexDirection, flexWrap: s.flexWrap, width: el.offsetWidth, height: el.offsetHeight };
      });
      const btnBoxes = await page.$$eval('.header-actions button', btns => btns.map(b => ({
        text: b.textContent.trim(),
        display: window.getComputedStyle(b).display,
        width: b.offsetWidth,
        height: b.offsetHeight,
        top: b.offsetTop,
        left: b.offsetLeft
      })));
      console.log('COMPACT_HEADER:', JSON.stringify(headerBox));
      console.log('HEADER_ACTIONS:', JSON.stringify(actionsBox));
      console.log('BUTTONS:', JSON.stringify(btnBoxes));
    }
  } else {
    console.log('NO_BANK_CARD');
  }
  await browser.close();
}

run().catch(console.error);
