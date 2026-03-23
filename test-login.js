const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  
  // 监听请求
  page.on('console', msg => console.log('CONSOLE:', msg.text()));
  page.on('request', req => {
    if (req.url().includes('auth')) {
      console.log('REQUEST:', req.method(), req.url());
    }
  });
  page.on('response', async res => {
    if (res.url().includes('auth')) {
      const text = await res.text();
      console.log('RESPONSE:', res.status(), res.url(), text.substring(0, 200));
    }
  });
  
  // 访问登录页
  await page.goto('https://blastjunior.com/login');
  await page.waitForLoadState('networkidle');
  
  // 输入邮箱
  await page.fill('#email', 'test@example.com');
  
  // 点击发送验证码
  await page.click('#sendCodeBtn');
  await page.waitForTimeout(3000);
  
  // 获取显示的验证码
  const toast = await page.textContent('.toast.show');
  console.log('Toast:', toast);
  
  // 提取验证码（6位数字）
  const codeMatch = toast.match(/(\d{6})/);
  if (codeMatch) {
    const code = codeMatch[1];
    console.log('Code:', code);
    
    // 输入验证码
    await page.fill('#code', code);
    
    // 点击登录
    await page.click('#loginBtn');
    await page.waitForTimeout(3000);
    
    // 检查当前URL
    console.log('Current URL:', page.url());
    
    // 检查localStorage
    const token = await page.evaluate(() => localStorage.getItem('blxst_token'));
    console.log('Token:', token);
  } else {
    console.log('No code found in toast');
  }
  
  await browser.close();
})();
