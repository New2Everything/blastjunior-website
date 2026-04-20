// 统一导航栏加载器
(function() {
  if (document.querySelector('.nav-wrap')) return;
  
  var navHTML = `<style>
.nav-wrap{background:var(--bg-white);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100}
.nav-inner{max-width:1200px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;padding:0 1.5rem;height:64px}
.nav-logo{display:flex;align-items:center;gap:0.75rem;font-family:var(--font-display);font-weight:900;font-size:1.2rem;color:var(--text-dark);text-decoration:none}
.nav-logo-icon{width:44px;height:44px;border-radius:10px;object-fit:contain;background:transparent}
.nav-links{display:flex;gap:0.25rem}
.nav-link{padding:0.5rem 1rem;border-radius:8px;text-decoration:none;color:var(--text-gray);font-weight:500;font-size:0.95rem;transition:all 0.2s}
.nav-link:hover{background:var(--bg-light);color:var(--text-dark)}
.nav-link.active{background:var(--primary);color:white}
.nav-actions{display:flex;align-items:center;gap:0.75rem}
.nav-btn{padding:0.5rem 1rem;border-radius:8px;font-weight:600;font-size:0.9rem;cursor:pointer;border:none;transition:all 0.2s;text-decoration:none}
.nav-btn-primary{background:var(--primary);color:white}
.nav-btn-outline{background:transparent;border:1px solid var(--border);color:var(--text-gray)}
.nav-btn:hover{opacity:0.9;transform:translateY(-1px)}
.nav-mobile-btn{display:none;background:none;border:none;cursor:pointer;padding:0.5rem}
.nav-mobile-btn span{display:block;width:22px;height:2px;background:var(--text-dark);margin:5px 0;transition:all 0.3s}
.nav-mobile-btn.active span:nth-child(1){transform:rotate(45deg) translate(5px,5px)}
.nav-mobile-btn.active span:nth-child(2){opacity:0}
.nav-mobile-btn.active span:nth-child(3){transform:rotate(-45deg) translate(5px,-5px)}
.nav-mobile-menu{display:none;position:fixed;top:64px;left:0;right:0;background:var(--bg-white);border-bottom:1px solid var(--border);padding:1rem;z-index:99;box-shadow:0 4px 12px rgba(0,0,0,0.1)}
.nav-mobile-menu.active{display:block}
.nav-mobile-link{display:block;padding:0.75rem 1rem;border-radius:8px;text-decoration:none;color:var(--text-gray);font-weight:500;transition:all 0.2s}
.nav-mobile-link:hover,.nav-mobile-link.active{background:var(--primary);color:white}
@media(max-width:768px){.nav-links,.nav-actions{display:none}.nav-mobile-btn{display:block}.nav-inner{height:56px}.nav-mobile-menu{top:56px}}
</style>
<div class="nav-wrap"><div class="nav-inner"><a href="/" class="nav-logo"><img src="/logo.jpg" alt="BLXST" class="nav-logo-icon"><span>BLXST</span></a><div class="nav-links"><a href="/" class="nav-link" data-page="home">首页</a><a href="/standings" class="nav-link" data-page="standings">积分榜</a><a href="/teams" class="nav-link" data-page="teams">战队</a><a href="/members" class="nav-link" data-page="members">成员</a><a href="/gallery" class="nav-link" data-page="gallery">画廊</a></div><div class="nav-actions" id="navActions"><a href="/login.html" class="nav-btn nav-btn-outline">登录</a><a href="/login.html" class="nav-btn nav-btn-primary">加入</a></div><button class="nav-mobile-btn" onclick="toggleMobileMenu()"><span></span><span></span><span></span></button></div><div class="nav-mobile-menu" id="mobileMenu"><a href="/" class="nav-mobile-link" data-page="home">首页</a><a href="/standings" class="nav-mobile-link" data-page="standings">积分榜</a><a href="/teams" class="nav-mobile-link" data-page="teams">战队</a><a href="/members" class="nav-mobile-link" data-page="members">成员</a><a href="/gallery" class="nav-mobile-link" data-page="gallery">画廊</a><hr style="border:none;border-top:1px solid var(--border);margin:0.5rem 0;"><a href="/login.html" class="nav-mobile-link" id="mobileAuth">登录/加入</a></div></div>
<script>
function toggleMobileMenu(){document.querySelector(".nav-mobile-btn").classList.toggle("active");document.getElementById("mobileMenu").classList.toggle("active")}
(function(){var p=location.pathname;document.querySelectorAll(".nav-link, .nav-mobile-link").forEach(function(l){var m=l.dataset.page;if(m==="home"?p==="/"||p==="/index.html":p.includes("/"+m))l.classList.add("active")}})();
(function(){var token=localStorage.getItem("blxst_token");if(token){var user=JSON.parse(localStorage.getItem("blxst_user")||"{}");var actions=document.getElementById("navActions");var isAdmin=user.role==='admin'||user.role==='leader';if(actions){actions.innerHTML=isAdmin?'<a href="/admin.html" class="nav-btn nav-btn-primary">⚙️ 管理</a>':'<a href="/profile.html" class="nav-btn nav-btn-outline">'+(user.nickname||"我")+"</a>"}var mobileAuth=document.getElementById("mobileAuth");if(mobileAuth){mobileAuth.href=isAdmin?"/admin.html":"/profile.html";mobileAuth.textContent=isAdmin?"管理后台":(user.nickname||"个人中心")}}})();
</script>`;
  
  var existingNav = document.querySelector('nav, .nav-wrap');
  if (existingNav) {
    existingNav.outerHTML = navHTML;
  } else {
    document.body.insertAdjacentHTML('afterbegin', navHTML);
  }
  if (window.innerWidth <= 768) document.body.style.paddingTop = '56px';
  else document.body.style.paddingTop = '64px';
})();
