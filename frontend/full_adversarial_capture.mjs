import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const OUT_DIR = path.resolve('docs/screenshots/adversarial_audit');
if (!fs.existsSync(OUT_DIR)) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
}

async function closeOpenDialog(page) {
  try {
    const btn = await page.$('.exam-setup-backdrop button:has-text("取消"), .exam-setup-backdrop button:has-text("关闭")');
    if (btn) {
      await btn.click();
      await page.waitForTimeout(300);
    }
  } catch (e) {}
}

async function capture() {
  const browser = await chromium.launch({ channel: 'msedge' });

  // 1. Desktop Context
  console.log('--- STARTING DESKTOP AUDIT (1440x900) ---');
  const dContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const dPage = await dContext.newPage();

  // Login
  await dPage.goto('http://192.168.100.11:3000', { waitUntil: 'networkidle' });
  await dPage.screenshot({ path: path.join(OUT_DIR, '01_desktop_login.png') });

  await dPage.locator('input[placeholder="用户名"]').fill('u_test_9435');
  await dPage.locator('input[placeholder*="密码"]').fill('Pass123456!');
  await dPage.locator('button:has-text("登录")').click();
  await dPage.waitForSelector('.page-header', { timeout: 10000 });
  await dPage.waitForTimeout(1000);

  // Home Desktop
  await dPage.screenshot({ path: path.join(OUT_DIR, '02_desktop_home.png') });

  // Modals on Home Desktop
  // Create Bank modal
  await dPage.locator('button:has-text("+ 创建题库")').click();
  await dPage.waitForTimeout(500);
  await dPage.screenshot({ path: path.join(OUT_DIR, '03_desktop_home_create_bank_modal.png') });
  await closeOpenDialog(dPage);

  // Blueprint modal
  const bpBtn = await dPage.$('button:has-text("蓝图")');
  if (bpBtn) {
    await bpBtn.click();
    await dPage.waitForTimeout(500);
    await dPage.screenshot({ path: path.join(OUT_DIR, '04_desktop_home_blueprint_modal.png') });
    await closeOpenDialog(dPage);
  }

  // AI Config modal
  const aiBtn = await dPage.$('button:has-text("AI配置")');
  if (aiBtn) {
    await aiBtn.click();
    await dPage.waitForTimeout(500);
    await dPage.screenshot({ path: path.join(OUT_DIR, '05_desktop_home_ai_config_modal.png') });
    await closeOpenDialog(dPage);
  }

  // Drafts modal
  const draftsBtn = await dPage.$('button:has-text("草稿箱")');
  if (draftsBtn) {
    await draftsBtn.click();
    await dPage.waitForTimeout(500);
    await dPage.screenshot({ path: path.join(OUT_DIR, '06_desktop_home_drafts_modal.png') });
    await closeOpenDialog(dPage);
  }

  // Assets modal
  const assetsBtn = await dPage.$('button:has-text("资料")');
  if (assetsBtn) {
    await assetsBtn.click();
    await dPage.waitForTimeout(500);
    await dPage.screenshot({ path: path.join(OUT_DIR, '07_desktop_home_assets_modal.png') });
    await closeOpenDialog(dPage);
  }

  // Learning View
  await dPage.locator('button:has-text("学习诊断")').click();
  await dPage.waitForTimeout(1000);
  await dPage.screenshot({ path: path.join(OUT_DIR, '08_desktop_learning_page.png') });
  await dPage.locator('.page-header button:has-text("返回")').click();
  await dPage.waitForTimeout(500);

  // Mistakes View
  await dPage.locator('button:has-text("错题与斩杀")').click();
  await dPage.waitForTimeout(1000);
  await dPage.screenshot({ path: path.join(OUT_DIR, '09_desktop_mistakes_page.png') });
  await dPage.locator('.page-header button:has-text("返回")').click();
  await dPage.waitForTimeout(500);

  // Import View
  await dPage.locator('button:has-text("导入题目")').click();
  await dPage.waitForTimeout(1000);
  await dPage.screenshot({ path: path.join(OUT_DIR, '10_desktop_import_page.png') });
  await dPage.locator('.page-header button:has-text("返回")').click();
  await dPage.waitForTimeout(500);

  // Exam Setup Dialog
  const examBtn = await dPage.$('.bank-card button:has-text("开始模考"):not([disabled])');
  if (examBtn) {
    await examBtn.click();
    await dPage.waitForTimeout(600);
    await dPage.screenshot({ path: path.join(OUT_DIR, '11_desktop_exam_setup_modal.png') });
    await closeOpenDialog(dPage);
  }

  // Enter Practice View
  const practiceBtn = await dPage.$('.bank-card button:has-text("开始刷题"):not([disabled])');
  if (practiceBtn) {
    await practiceBtn.click();
    await dPage.waitForSelector('.practice-page', { timeout: 8000 });
    await dPage.waitForTimeout(800);
    // Practice unanswered
    await dPage.screenshot({ path: path.join(OUT_DIR, '12_desktop_practice_unanswered.png') });

      // Practice Sheet Modal
      const sheetPill = await dPage.$('.btn-sheet-trigger-pill');
      if (sheetPill) {
        await sheetPill.click();
        await dPage.waitForTimeout(500);
        await dPage.screenshot({ path: path.join(OUT_DIR, '13_desktop_practice_sheet_modal.png') });
        const closeSheet = await dPage.$('.btn-close-sheet');
        if (closeSheet) await closeSheet.click();
        await dPage.waitForTimeout(300);
      }

      // Practice Guide Modal
      const guideBtn = await dPage.$('.btn-help-guide');
      if (guideBtn) {
        await guideBtn.click();
        await dPage.waitForTimeout(500);
        await dPage.screenshot({ path: path.join(OUT_DIR, '14_desktop_practice_guide_modal.png') });
        const closeGuide = await dPage.$('.btn-close-tip');
        if (closeGuide) await closeGuide.click();
        await dPage.waitForTimeout(300);
      }

      // Select an option and submit to see Answered State
      const opt = await dPage.$('.option-item, .option-btn, .option-row');
      if (opt) {
        await opt.click();
        await dPage.waitForTimeout(300);
        const submitBtn = await dPage.$('button:has-text("提交答案")');
        if (submitBtn) {
          await submitBtn.click();
          await dPage.waitForTimeout(1000);
          await dPage.screenshot({ path: path.join(OUT_DIR, '15_desktop_practice_answered_explanation.png') });
        }
      }

      // Back to home
      const backBtn = await dPage.$('.btn-back');
      if (backBtn) {
        await backBtn.click();
        await dPage.waitForTimeout(500);
      }
    }

  // 2. Mobile Context (390x844 iPhone 13/14 size)
  console.log('--- STARTING MOBILE AUDIT (390x844) ---');
  const mContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
  });
  const mPage = await mContext.newPage();
  await mPage.goto('http://192.168.100.11:3000', { waitUntil: 'networkidle' });

  // Mobile Login
  await mPage.screenshot({ path: path.join(OUT_DIR, '20_mobile_login.png') });
  await mPage.locator('input[placeholder="用户名"]').fill('u_test_9435');
  await mPage.locator('input[placeholder*="密码"]').fill('Pass123456!');
  await mPage.locator('button:has-text("登录")').click();
  await mPage.waitForSelector('.page-header', { timeout: 10000 });
  await mPage.waitForTimeout(1000);

  // Mobile Home
  await mPage.screenshot({ path: path.join(OUT_DIR, '21_mobile_home.png') });

  // Mobile Learning
  await mPage.locator('button:has-text("学习诊断")').click();
  await mPage.waitForTimeout(1000);
  await mPage.screenshot({ path: path.join(OUT_DIR, '22_mobile_learning.png') });
  await mPage.locator('.page-header button:has-text("返回")').click();
  await mPage.waitForTimeout(500);

  // Mobile Mistakes
  await mPage.locator('button:has-text("错题与斩杀")').click();
  await mPage.waitForTimeout(1000);
  await mPage.screenshot({ path: path.join(OUT_DIR, '23_mobile_mistakes.png') });
  await mPage.locator('.page-header button:has-text("返回")').click();
  await mPage.waitForTimeout(500);

  // Mobile Import
  await mPage.locator('button:has-text("导入题目")').click();
  await mPage.waitForTimeout(1000);
  await mPage.screenshot({ path: path.join(OUT_DIR, '24_mobile_import.png') });
  await mPage.locator('.page-header button:has-text("返回")').click();
  await mPage.waitForTimeout(500);

  // Mobile Practice
  const mPracticeBtn = await mPage.$('.bank-card button:has-text("开始刷题"):not([disabled])');
  if (mPracticeBtn) {
    await mPracticeBtn.click();
    await mPage.waitForSelector('.practice-page', { timeout: 8000 });
    await mPage.waitForTimeout(800);
    await mPage.screenshot({ path: path.join(OUT_DIR, '25_mobile_practice_unanswered.png') });

      // Mobile More Menu
      const moreBtn = await mPage.$('.btn-more-menu');
      if (moreBtn) {
        await moreBtn.click();
        await mPage.waitForTimeout(400);
        await mPage.screenshot({ path: path.join(OUT_DIR, '26_mobile_practice_more_menu.png') });
        await moreBtn.click();
        await mPage.waitForTimeout(200);
      }

      // Mobile Sheet
      const mSheetPill = await mPage.$('.btn-sheet-trigger-pill');
      if (mSheetPill) {
        await mSheetPill.click();
        await mPage.waitForTimeout(500);
        await mPage.screenshot({ path: path.join(OUT_DIR, '27_mobile_practice_sheet_drawer.png') });
      }
    }

  console.log('--- ALL AUDIT SCREENSHOTS CAPTURED SUCCESSFULLY ---');
  await browser.close();
}

capture().catch(err => {
  console.error('AUDIT_CAPTURE_ERROR:', err);
  process.exit(1);
});
