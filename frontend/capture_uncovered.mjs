import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const OUT_DIR = path.resolve('docs/screenshots/adversarial_audit');
if (!fs.existsSync(OUT_DIR)) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
}

async function capture() {
  const browser = await chromium.launch({ channel: 'msedge' });

  // ===================== DESKTOP =====================
  console.log('--- STARTING UNCOVERED DESKTOP AUDIT ---');
  const dContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const dPage = await dContext.newPage();

  // 1. Register state in Login
  await dPage.goto('http://192.168.100.11:3000', { waitUntil: 'networkidle' });
  const signupLink = await dPage.$('text=创建账号');
  if (signupLink) {
    await signupLink.click();
    await dPage.waitForTimeout(400);
    await dPage.screenshot({ path: path.join(OUT_DIR, '30_desktop_register_form.png') });
  }

  // Login
  await dPage.goto('http://192.168.100.11:3000', { waitUntil: 'networkidle' });
  await dPage.locator('input[placeholder="用户名"]').fill('u_test_9435');
  await dPage.locator('input[placeholder*="密码"]').fill('Pass123456!');
  await dPage.locator('button:has-text("登录")').click();
  await dPage.waitForSelector('.page-header', { timeout: 10000 });
  await dPage.waitForTimeout(1000);

  // 2. Bank card modals: + 录入, 共享, 导出
  const bankCard = await dPage.$('.bank-card');
  if (bankCard) {
    // + 录入
    const addQBtn = await bankCard.$('button:has-text("+ 录入")');
    if (addQBtn) {
      await addQBtn.click();
      await dPage.waitForTimeout(500);
      await dPage.screenshot({ path: path.join(OUT_DIR, '31_desktop_home_add_question_modal.png') });
      const cancel = await dPage.$('.exam-setup-backdrop button:has-text("取消")');
      if (cancel) await cancel.click();
      await dPage.waitForTimeout(300);
    }
    // 共享
    const shareBtn = await bankCard.$('button:has-text("共享")');
    if (shareBtn) {
      await shareBtn.click();
      await dPage.waitForTimeout(500);
      await dPage.screenshot({ path: path.join(OUT_DIR, '32_desktop_home_share_modal.png') });
      const close = await dPage.$('.exam-setup-backdrop button:has-text("关闭")');
      if (close) await close.click();
      await dPage.waitForTimeout(300);
    }
    // 导出
    const exportBtn = await bankCard.$('button:has-text("导出")');
    if (exportBtn) {
      await exportBtn.click();
      await dPage.waitForTimeout(500);
      await dPage.screenshot({ path: path.join(OUT_DIR, '33_desktop_home_export_modal.png') });
      const cancel = await dPage.$('.exam-setup-backdrop button:has-text("取消")');
      if (cancel) await cancel.click();
      await dPage.waitForTimeout(300);
    }
  }

  // 3. Mistakes View - Tab 2 (斩杀题库)
  await dPage.locator('button:has-text("错题与斩杀")').click();
  await dPage.waitForTimeout(1000);
  const killTab = await dPage.$('button:has-text("斩杀题库")');
  if (killTab) {
    await killTab.click();
    await dPage.waitForTimeout(500);
    await dPage.screenshot({ path: path.join(OUT_DIR, '34_desktop_mistakes_kills_tab.png') });
  }
  await dPage.locator('.page-header button:has-text("返回")').click();
  await dPage.waitForTimeout(500);

  // 4. Practice View: Answered state & Completion report
  const practiceBtn = await dPage.$('.bank-card button:has-text("开始刷题"):not([disabled])');
  if (practiceBtn) {
    await practiceBtn.click();
    await dPage.waitForSelector('.practice-page', { timeout: 8000 });
    await dPage.waitForTimeout(800);

    // Click option
    const opt = await dPage.$('.option-item, .option-btn, .option-row');
    if (opt) {
      await opt.click();
      await dPage.waitForTimeout(300);
      const submitAnswer = await dPage.$('button:has-text("提交答案")');
      if (submitAnswer) {
        await submitAnswer.click();
        await dPage.waitForTimeout(1000);
        // Screenshot answered state with explanation & FSRS rating
        await dPage.screenshot({ path: path.join(OUT_DIR, '35_desktop_practice_answered_explanation.png') });
      }
    }

    // Now click 交卷 to test Practice Completion Dialog & Result Modal
    const completeBtn = await dPage.$('button:has-text("交卷")');
    if (completeBtn) {
      await completeBtn.click();
      await dPage.waitForTimeout(600);
      // Capture confirm modal if present
      await dPage.screenshot({ path: path.join(OUT_DIR, '36a_desktop_practice_confirm_modal.png') });
      const confirmBtn = await dPage.$('.confirm-submit-dialog button:has-text("确认交卷")');
      if (confirmBtn) {
        await confirmBtn.click();
        await dPage.waitForTimeout(1000);
      }
      // Screenshot practice report card modal
      await dPage.screenshot({ path: path.join(OUT_DIR, '36b_desktop_practice_result_modal.png') });
      // Back to home from modal
      const backFromModal = await dPage.$('.practice-result-card-modal button:has-text("返回题库")');
      if (backFromModal) {
        await backFromModal.click();
      } else {
        const backHome = await dPage.$('button:has-text("返回题库"), .btn-back');
        if (backHome) await backHome.click({ force: true });
      }
      await dPage.waitForTimeout(800);
    }
  }

  // 5. Exam View: Start Exam, in progress, confirm modal, report
  const examBtn = await dPage.$('.bank-card button:has-text("开始模考"):not([disabled])');
  if (examBtn) {
    await examBtn.click();
    await dPage.waitForTimeout(600);
    // Click 开始考试 inside modal
    const startExamModalBtn = await dPage.$('.exam-setup-dialog button:has-text("开始考试")');
    if (startExamModalBtn) {
      await startExamModalBtn.click();
      await dPage.waitForSelector('.exam-page', { timeout: 8000 });
      await dPage.waitForTimeout(1000);
      // Screenshot active exam page
      await dPage.screenshot({ path: path.join(OUT_DIR, '37_desktop_exam_active.png') });

      // Click 交卷 to open Confirm Dialog
      const examSubmitBtn = await dPage.$('.exam-header button:has-text("交卷")');
      if (examSubmitBtn) {
        await examSubmitBtn.click();
        await dPage.waitForTimeout(500);
        await dPage.screenshot({ path: path.join(OUT_DIR, '38_desktop_exam_submit_confirm_dialog.png') });

        // Confirm submit
        const confirmYes = await dPage.$('button:has-text("确认交卷")');
        if (confirmYes) {
          await confirmYes.click();
          await dPage.waitForTimeout(1200);
          await dPage.screenshot({ path: path.join(OUT_DIR, '39_desktop_exam_report_page.png') });
        }
      }
    }
  }

  // ===================== MOBILE =====================
  console.log('--- STARTING UNCOVERED MOBILE AUDIT (390x844) ---');
  const mContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
  });
  const mPage = await mContext.newPage();
  await mPage.goto('http://192.168.100.11:3000', { waitUntil: 'networkidle' });
  await mPage.locator('input[placeholder="用户名"]').fill('u_test_9435');
  await mPage.locator('input[placeholder*="密码"]').fill('Pass123456!');
  await mPage.locator('button:has-text("登录")').click();
  await mPage.waitForSelector('.page-header', { timeout: 10000 });
  await mPage.waitForTimeout(1000);

  // Mobile Exam
  const mExamBtn = await mPage.$('.bank-card button:has-text("开始模考"):not([disabled])');
  if (mExamBtn) {
    await mExamBtn.click();
    await mPage.waitForTimeout(600);
    const mStartExamModalBtn = await mPage.$('.exam-setup-dialog button:has-text("开始考试")');
    if (mStartExamModalBtn) {
      await mStartExamModalBtn.click();
      await mPage.waitForSelector('.exam-page', { timeout: 8000 });
      await mPage.waitForTimeout(800);
      await mPage.screenshot({ path: path.join(OUT_DIR, '40_mobile_exam_active.png') });

      // Mobile exam sheet trigger
      const mSheetBtn = await mPage.$('.btn-exam-sheet-trigger, .exam-header-center');
      if (mSheetBtn) {
        await mSheetBtn.click();
        await mPage.waitForTimeout(500);
        await mPage.screenshot({ path: path.join(OUT_DIR, '41_mobile_exam_sheet_drawer.png') });
      }
    }
  }

  console.log('--- ALL UNCOVERED SCREENSHOTS CAPTURED ---');
  await browser.close();
}

capture().catch(err => {
  console.error('CAPTURE_ERROR:', err);
  process.exit(1);
});
