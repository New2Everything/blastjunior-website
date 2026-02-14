<script>
  import { onMount } from 'svelte';
  import { fetchCampaigns } from '$lib/api';
  
  let isMobile = false;
  let campaigns = [];
  let isLoading = true;
  let error = null;
  
  onMount(() => {
    // Check if user is on mobile
    isMobile = window.innerWidth < 768;
    
    // Add resize listener
    const handleResize = () => {
      isMobile = window.innerWidth < 768;
    };
    
    window.addEventListener('resize', handleResize);
    
    // Load campaigns data from API
    loadCampaigns();
    
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  });
  
  async function loadCampaigns() {
    try {
      campaigns = await fetchCampaigns();
      isLoading = false;
    } catch (err) {
      error = "Failed to load campaigns";
      isLoading = false;
      console.error(err);
    }
  }
</script>

<link rel="stylesheet" href="./+page.css">

<div class="container">
  <header class="header">
    <div class="logo">HADO</div>
    <div class="tagline">Powerful Campaign Management Platform</div>
  </header>
  
  <main>
    <section class="hero">
      <h1>Welcome to HADO</h1>
      <p>Manage your marketing campaigns with ease and precision. Track performance, engage audiences, and drive results.</p>
      <button class="cta-button">Get Started</button>
    </section>
    
    <section class="campaigns-section">
      <h2 class="section-title">Your Campaigns</h2>
      
      {#if isLoading}
        <div class="loading">Loading campaigns...</div>
      {:else if error}
        <div class="error">{error}</div>
      {:else}
        <div class="campaigns-grid">
          {#each campaigns as campaign}
            <div class="campaign-card">
              <div class="campaign-name">{campaign.name}</div>
              <span class="campaign-status status-{campaign.status}">{campaign.status}</span>
              <div class="campaign-reach">Reach: {campaign.reach.toLocaleString()}</div>
            </div>
          {/each}
        </div>
      {/if}
    </section>
  </main>
</div>