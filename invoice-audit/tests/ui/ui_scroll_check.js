// 验证配置页/数据看板可滚动 + 员工页新流程图渲染
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.setDefaultTimeout(15000);
  const out = {};

  // 登录 admin
  await page.goto('http://localhost:8000/login', { waitUntil: 'networkidle' });
  await page.fill('input[placeholder*="员工工号"]', 'admin');
  await page.fill('input[type="password"]', 'admin');
  await page.click('button:has-text("登 录")');
  await page.waitForURL('**/home/**');

  async function checkScroll(label) {
    const m = await page.evaluate(() => {
      const el = document.querySelector('.page');
      if (!el) return { found: false };
      return {
        found: true,
        clientH: el.clientHeight,
        scrollH: el.scrollHeight,
        scrollable: el.scrollHeight > el.clientHeight + 2,
      };
    });
    if (m.found && m.scrollable) {
      await page.evaluate(() => {
        document.querySelector('.page').scrollTop = 99999;
      });
      await page.waitForTimeout(400);
      const top = await page.evaluate(() => document.querySelector('.page').scrollTop);
      out[label] = { ...m, scrolledTo: top, scrollWorks: top > 0 };
    } else {
      out[label] = m;
    }
  }

  await page.click('button:has-text("模型调参")');
  await page.waitForSelector('text=视觉模型配置');
  await page.waitForTimeout(600);
  await checkScroll('配置页');

  await page.click('button:has-text("数据看板")');
  await page.waitForSelector('text=报销单全表');
  await page.waitForTimeout(600);
  await checkScroll('数据看板');

  // 员工页新流程渲染验证（借一个员工账号看历史单据详情）
  await page.click('button:has-text("退出")');
  await page.waitForURL('**/login**');
  await page.fill('input[placeholder*="员工工号"]', 'TEST0001');
  await page.fill('input[type="password"]', 'test123456');
  await page.click('button:has-text("登 录")');
  await page.waitForSelector('text=提交报销表单');
  await page.waitForTimeout(1500);
  const flowTexts = await page.evaluate(() => {
    const t = document.body.innerText;
    return {
      hasVision: t.includes('视觉模型审核'),
      hasLlm: t.includes('语言模型审核'),
      hasManual: t.includes('人工审核'),
      hasSubmit: t.includes('已提交'),
      hasDone: t.includes('完成'),
      hasPerson: !!document.querySelector('.wp-svg'),
    };
  });
  out['员工页流程'] = flowTexts;
  await page.screenshot({ path: __dirname + '/screenshots/08-employee-flow.png', fullPage: true });

  await browser.close();
  console.log(JSON.stringify(out, null, 2));
  const allOk = Object.values(out).every((v) => {
    if (v && typeof v === 'object') {
      if ('scrollable' in v) return v.scrollable && v.scrollWorks;
      return Object.values(v).every(Boolean);
    }
    return false;
  });
  process.exit(allOk ? 0 : 1);
})().catch((e) => { console.error('SCROLL CHECK FAILED:', e.message); process.exit(1); });
