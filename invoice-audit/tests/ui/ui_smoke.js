// UI 冒烟测试（Playwright + Edge，Windows 访问；地址与样本路径可用环境变量覆盖）
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = process.env.TEST_BASE || 'http://localhost:8000';
const SHOT = path.join(__dirname, 'screenshots');
// 样本自动探测：TEST_INVOICE > <工作区>/发票汇总/trip.pdf
const wsDir = path.resolve(__dirname, '../../../..'); // tests/ui -> 工作区根
const INVOICE_FILE = process.env.TEST_INVOICE ||
  (fs.existsSync(path.join(wsDir, '发票汇总', 'trip.pdf'))
    ? path.join(wsDir, '发票汇总', 'trip.pdf')
    : path.join(wsDir, 'trip.pdf'));
const results = [];

function record(name, cond, extra = '') {
  results.push({ name, pass: !!cond, extra });
  if (!cond) throw new Error(`${name} FAILED ${extra}`);
}

(async () => {
  fs.mkdirSync(SHOT, { recursive: true });
  let browser;
  try {
    browser = await chromium.launch({ channel: 'msedge' }); // 本机 Edge，免下载
  } catch (e) {
    browser = await chromium.launch(); // 回退到已安装的 Chromium
  }
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.setDefaultTimeout(15000);

  // 1. 登录页
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' });
  record('登录页渲染', await page.locator('text=发票审计系统').first().isVisible());
  await page.screenshot({ path: path.join(SHOT, '01-login.png') });

  // 2. 管理员 admin/admin 登录 → 应直达审查工作台
  await page.fill('input[placeholder*="员工工号"]', 'admin');
  await page.fill('input[type="password"]', 'admin');
  await page.click('button:has-text("登 录")');
  await page.waitForURL('**/home/**');
  await page.waitForSelector('text=待人工审查队列');
  record('admin登录直达审查工作台', page.url().includes('reviewer'), page.url());
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(SHOT, '02-reviewer.png') });

  // 3. 右侧系统状态面板
  record('系统状态面板', await page.locator('text=GPU').first().isVisible());

  // 4. 数据看板
  await page.click('button:has-text("数据看板")');
  await page.waitForSelector('text=报销单全表');
  await page.waitForTimeout(1000);
  const rows = await page.locator('.el-table__row').count();
  record('看板表格有数据', rows > 0, `rows=${rows}`);
  record('看板统计卡片', await page.locator('text=报销单总数').first().isVisible());
  await page.screenshot({ path: path.join(SHOT, '03-dashboard.png') });

  // 5. 模型调参页
  await page.click('button:has-text("模型调参")');
  await page.waitForSelector('text=视觉模型配置');
  record('调参页表单', await page.locator('text=系统提示词').isVisible());
  await page.screenshot({ path: path.join(SHOT, '04-config.png') });

  // 6. 系统监控页
  await page.click('button:has-text("系统状态")');
  await page.waitForSelector('text=系统状态监控');
  await page.waitForTimeout(1500);
  record('监控页GPU卡片', await page.locator('text=GPU').first().isVisible());
  await page.screenshot({ path: path.join(SHOT, '05-monitor.png') });

  // 7. 退出 → 注册新员工（下拉选项来自枚举接口）
  await page.click('button:has-text("退出")');
  await page.waitForURL('**/login**');
  const emp = 'UI' + String(Date.now()).slice(-6);
  await page.click('a:has-text("员工注册")');
  await page.waitForSelector('text=员工工号');
  await page.fill('input[placeholder="8位字母或数字"]', emp);
  await page.fill('.el-dialog .el-form-item:has-text("员工名字") input', 'UI测试员');
  await page.locator('.el-dialog .el-select').nth(0).click();
  await page.click('.el-select-dropdown__item:has-text("技术部")');
  await page.locator('.el-dialog .el-select').nth(1).click();
  await page.click('.el-select-dropdown__item:has-text("P3")');
  await page.locator('.el-dialog .el-select').nth(2).click();
  await page.click('.el-select-dropdown__item:has-text("工程师")');
  await page.fill('input[placeholder="至少6位"]', 'Uipass123');
  await page.click('.el-dialog button:has-text("注册")');
  await page.waitForSelector('text=注册成功');
  record('员工注册(含枚举下拉)', true);
  await page.screenshot({ path: path.join(SHOT, '06-register.png') });

  // 8. 员工登录 → 上传一张发票 → 历史列表出现并走到终态
  await page.fill('input[placeholder*="员工工号"]', emp);
  await page.fill('input[type="password"]', 'Uipass123');
  await page.click('button:has-text("登 录")');
  await page.waitForURL('**/home/**');
  await page.waitForSelector('text=提交报销表单');
  record('员工登录直达上传页', page.url().includes('employee'), page.url());
  const invoice = INVOICE_FILE;
  await page.setInputFiles('input[type="file"]', invoice);
  await page.fill('textarea[placeholder*="报销备注"]', 'UI冒烟测试备注');
  await page.click('button:has-text("确认提交")');
  await page.waitForSelector('text=进入审核流程');
  record('员工上传发票成功', true);
  // 轮询历史列表出现终态标签（最多 90s）
  let terminal = false;
  for (let i = 0; i < 18; i++) {
    await page.waitForTimeout(5000);
    const done = await page.locator('.rec-item :text("已报销"), .rec-item :text("不报销"), .rec-item :text("待人工审查"), .rec-item :text("系统异常")').count();
    if (done > 0) { terminal = true; break; }
  }
  record('单据流转至终态展示', terminal);
  await page.screenshot({ path: path.join(SHOT, '07-employee-final.png') });

  await browser.close();
  console.log(JSON.stringify(results, null, 2));
  process.exit(results.every((r) => r.pass) ? 0 : 1);
})().catch((e) => {
  console.error('UI SMOKE FAILED:', e.message);
  console.log(JSON.stringify(results, null, 2));
  process.exit(1);
});
