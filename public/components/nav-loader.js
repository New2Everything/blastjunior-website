// 动态加载统一导航栏
async function loadNav() {
  try {
    const response = await fetch('/components/nav.html');
    const navHTML = await response.text();
    
    // 找到 body 中的第一个 nav 元素并替换，或者插入到 body 开头
    const existingNav = document.querySelector('nav');
    if (existingNav) {
      existingNav.outerHTML = navHTML;
    } else {
      document.body.insertAdjacentHTML('afterbegin', navHTML);
    }
    
    // 添加 body padding 以防止导航栏遮挡内容
    document.body.style.paddingTop = '64px';
    
    // 移动端 padding 调整
    if (window.innerWidth <= 768) {
      document.body.style.paddingTop = '56px';
    }
  } catch (e) {
    console.error('加载导航栏失败:', e);
  }
}

// 页面加载后执行
document.addEventListener('DOMContentLoaded', loadNav);
