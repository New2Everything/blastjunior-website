<script>
  // 照片页面 - 严格遵循设计方案
  import { onMount } from 'svelte';
  
  let photos = [];
  let selectedPhoto = null;
  let comments = [];
  let newComment = '';
  
  // 获取随机照片
  async function fetchRandomPhotos() {
    const res = await fetch('/media/list');
    const data = await res.json();
    // 随机打乱 + 取前50
    const shuffled = data.items.sort(() => 0.5 - Math.random());
    photos = shuffled.slice(0, 50);
  }
  
  // 打开照片详情
  async function openPhoto(photo) {
    selectedPhoto = photo;
    const res = await fetch(`/comments?photoId=${photo.id}`);
    const data = await res.json();
    comments = data.items || [];
  }
  
  // 提交评论
  async function submitComment() {
    if (!newComment.trim()) return;
    
    await fetch('/comments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        photoId: selectedPhoto.id,
        content: newComment,
        nickname: '游客'
      })
    });
    
    newComment = '';
    // 刷新评论
    const res = await fetch(`/comments?photoId=${selectedPhoto.id}`);
    const data = await res.json();
    comments = data.items || [];
  }
  
  // 生成九宫格
  async function generateGrid() {
    // 从当前照片中随机选9张
    const gridPhotos = [...photos].sort(() => 0.5 - Math.random()).slice(0, 9);
    
    // 创建 Canvas
    const canvas = document.createElement('canvas');
    canvas.width = 900;
    canvas.height = 900;
    const ctx = canvas.getContext('2d');
    
    // 绘制九宫格
    for (let i = 0; i < 9; i++) {
      const img = new Image();
      img.src = gridPhotos[i].thumb;
      await new Promise(resolve => {
        img.onload = () => {
          const x = (i % 3) * 300;
          const y = Math.floor(i / 3) * 300;
          ctx.drawImage(img, x, y, 300, 300);
          resolve();
        };
      });
    }
    
    // 下载
    const link = document.createElement('a');
    link.download = 'hado-grid.png';
    link.href = canvas.toDataURL();
    link.click();
  }
  
  onMount(() => {
    fetchRandomPhotos();
  });
</script>

<div class="gallery-page">
  <!-- 九宫格生成按钮 -->
  <button on:click={generateGrid} class="grid-btn">生成九宫格海报</button>
  
  <!-- 照片墙 -->
  <div class="photo-grid">
    {#each photos as photo}
      <div class="photo-item" on:click={() => openPhoto(photo)}>
        <img src={photo.thumb} alt="HADO 活动照片" loading="lazy" />
      </div>
    {/each}
  </div>
  
  <!-- 照片详情弹窗 -->
  {#if selectedPhoto}
    <div class="modal" on:click={() => selectedPhoto = null}>
      <div class="modal-content" on:click|stopPropagation>
        <img src={selectedPhoto.web} alt="高清照片" />
        <div class="comments">
          <h3>留言 ({comments.length})</h3>
          <div class="comment-list">
            {#each comments as comment}
              <div class="comment">
                <strong>{comment.nickname}</strong>
                <p>{comment.content}</p>
              </div>
            {/each}
          </div>
          <form on:submit|preventDefault={submitComment}>
            <textarea bind:value={newComment} placeholder="写下你的留言..."></textarea>
            <button type="submit">提交</button>
          </form>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .gallery-page {
    padding: 20px;
  }
  
  .grid-btn {
    background: #ff4757;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 5px;
    margin-bottom: 20px;
    cursor: pointer;
  }
  
  .photo-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 10px;
  }
  
  .photo-item {
    cursor: pointer;
    border-radius: 8px;
    overflow: hidden;
    aspect-ratio: 1/1;
  }
  
  .photo-item img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  
  .modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.8);
    display: flex;
    justify-content: center;
    align-items: center;
  }
  
  .modal-content {
    display: flex;
    gap: 20px;
    max-width: 90%;
    max-height: 90%;
    background: white;
    padding: 20px;
    border-radius: 10px;
  }
  
  .modal-content img {
    max-width: 600px;
    max-height: 600px;
    object-fit: contain;
  }
  
  .comments {
    width: 300px;
    overflow-y: auto;
    max-height: 600px;
  }
  
  textarea {
    width: 100%;
    height: 80px;
    margin-top: 10px;
  }
</style>