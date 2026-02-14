<script>
  // 首页实现 - 严格遵循设计方案
  import { onMount } from 'svelte';
  
  let heroParticles = false;
  let leagueData = [];
  
  // 初始化 HADO 粒子动画
  onMount(() => {
    heroParticles = true;
    // 模拟粒子动画初始化
    console.log('HADO 粒子动画已启动');
    
    // 获取实时联赛数据
    fetch('/api/public/campaigns_bundle?event_id=internal_league')
      .then(r => r.json())
      .then(data => {
        leagueData = data.table.slice(0, 3); // Top 3
      });
  });
</script>

<!-- HERO 区域 -->
<section class="hero">
  {#if heroParticles}
    <div class="particle-canvas" id="hado-particles"></div>
  {/if}
  <h1>兰星少年俱乐部<br/>让 HADO 少年发光</h1>
  <p>中国 HADO 业余俱乐部 · 科技运动 · 团队竞技</p>
</section>

<!-- 实时积分榜 -->
<section class="league-preview">
  <h2>内部联赛 · 实时排名</h2>
  <ul>
    {#each leagueData as team, i}
      <li class="rank-item">
        <span class="rank">{i+1}</span>
        <span class="team-name">{team.team_name}</span>
        <span class="points">{team.points} 分</span>
      </li>
    {/each}
  </ul>
</section>

<style>
  .hero {
    position: relative;
    height: 80vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
  }
  
  .particle-canvas {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: -1;
  }
  
  .league-preview {
    padding: 2rem;
  }
  
  .rank-item {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem 0;
    border-bottom: 1px solid #334155;
  }
</style>