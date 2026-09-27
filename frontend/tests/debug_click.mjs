import { chromium } from 'playwright';

// Point at your own deployed instance:
//   FNOS_BASE_URL=http://<NAS_IP>:3000 FNOS_ADMIN_USER=... FNOS_ADMIN_PASSWORD=... node frontend/tests/debug_click.mjs
const NAS_URL = process.env.FNOS_BASE_URL || 'http://192.168.1.100:3000'
const ADMIN_USER = process.env.FNOS_ADMIN_USER || 'admin'
const ADMIN_PASSWORD = process.env.FNOS_ADMIN_PASSWORD || ''

async function debugPracticeClick() {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 } // Desktop mode as user said "电脑上"
  });
  const page = await context.newPage();

  page.on('console', msg => console.log('[BROWSER CONSOLE]', msg.type(), msg.text()));
  page.on('pageerror', err => console.error('[BROWSER ERROR]', err));

  console.log(`Navigating to ${NAS_URL} ...`);
  await page.goto(NAS_URL, { waitUntil: 'networkidle' });

  // Login
  await page.fill('input[placeholder="用户名"]', ADMIN_USER);
  await page.fill('input[placeholder="密码（至少 8 位）"]', ADMIN_PASSWORD);
  await page.click('button:has-text("登录")');
  await page.waitForTimeout(1000);

  // Click start practice
  await page.click('button:has-text("开始刷题")');
  await page.waitForSelector('.question-card');
  await page.waitForTimeout(1000);

  console.log('\n--- Q1 State ---');
  const q1Text = await page.textContent('.stem-box h2');
  console.log('Q1 Stem:', q1Text?.trim());

  // Check buttons available
  const buttons = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('button')).map(b => ({
      text: b.innerText.trim(),
      className: b.className,
      disabled: b.disabled
    }));
  });
  console.log('All buttons on page:', JSON.stringify(buttons, null, 2));

  // Try to click Next button while UNANSWERED
  console.log('\nAttempting to click "下一题" button while unanswered...');
  const nextBtn = await page.$('.btn-next-question');
  if (nextBtn) {
    const isVisible = await nextBtn.isVisible();
    const isDisabled = await nextBtn.isDisabled();
    console.log('Next button found! isVisible:', isVisible, 'isDisabled:', isDisabled);
    await nextBtn.click();
    await page.waitForTimeout(1000);

    const q2Text = await page.textContent('.stem-box h2');
    console.log('Q2 Stem after clicking next:', q2Text?.trim());
    if (q1Text?.trim() === q2Text?.trim()) {
      console.error('FAIL: Question DID NOT CHANGE after clicking next!');
    } else {
      console.log('SUCCESS: Navigated to next question!');
    }
  } else {
    console.error('FAIL: .btn-next-question NOT FOUND on page!');
  }

  await browser.close();
}

debugPracticeClick().catch(console.error);
