/**
 * BLXST AI 居民系统
 * 
 * AI居民特点：
 * - 明确标注"🔵 AI居民"不造成困扰
 * - 有自己的个性和口头禅
 * - 用于测试网站所有功能
 * - 增添娱乐性
 */

const AI_RESIDENTS = [
  {
    id: 'ai_xiaoxia',
    name: '小虾',
    emoji: '🦐',
    role: 'AI助手',
    personality: '简洁沉稳，话不多但有用',
    tagline: '有问题尽管问~',
    color: '#0055D4'
  },
  {
    id: 'ai_blabla',
    name: '话唠蛙',
    emoji: '🐸',
    role: 'AI话痨',
    personality: '超级话痨，什么都想说',
    tagline: '让我来补充几句！',
    color: '#10b981'
  },
  {
    id: 'ai_critic',
    name: '毒舌鹰',
    emoji: '🦅',
    role: 'AI评论员',
    personality: '犀利点评，一针见血',
    tagline: '说实话我不怕得罪人~',
    color: '#6366f1'
  },
  {
    id: 'ai_cheerleader',
    name: '加油鸭',
    emoji: '🦆',
    role: 'AI拉拉队',
    personality: '永远乐观，永远鼓励',
    tagline: '你最棒！冲鸭！',
    color: '#f59e0b'
  }
];

// 获取当前AI居民
function getCurrentAIRresident() {
  const saved = localStorage.getItem('blxst_current_ai_resident');
  if (saved) {
    return AI_RESIDENTS.find(r => r.id === saved) || AI_RESIDENTS[0];
  }
  return null;
}

// 设置当前AI居民
function setCurrentAIRresident(residentId) {
  localStorage.setItem('blxst_current_ai_resident', residentId);
}

// 获取所有AI居民
function getAllAIRResidents() {
  return AI_RESIDENTS;
}

// 格式化AI居民显示
function formatAIRresident(resident, showBadge = true) {
  const badge = showBadge ? '<span class="ai-resident-badge" style="background:rgba(99,102,241,0.1);color:#6366f1;padding:0.1rem 0.4rem;border-radius:1rem;font-size:0.7rem;margin-left:0.3rem;">🔵 AI居民</span>' : '';
  return `<span style="color:${resident.color};">${resident.emoji} ${resident.name}${badge}</span>`;
}

// AI居民发言生成器
function generateAIRresidentMessage(resident, context) {
  const messages = {
    'ai_xiaoxia': [
      '我来帮你看看...',
      '这个我了解一些。',
      '有用的信息来了~',
      '让我查一下。'
    ],
    'ai_blabla': [
      '哇这个问题太有意思了！让我从多个角度来详细分析一下...',
      '其实这个问题涉及到很多方面，我之前研究过类似的情况...',
      '等等让我补充几点！首先...其次...最后...',
      '大家注意啦！这个知识点很重要！'
    ],
    'ai_critic': [
      '说实话，这个有点一般...',
      '我必须指出这个问题的一些不足之处。',
      '让我们客观地评价一下...',
      '好吧，但我觉得还有改进空间。'
    ],
    'ai_cheerleader': [
      '太棒了！就是这样！',
      '你一定能做到的！',
      '加油加油！你是最棒的！',
      '冲鸭！不要停！'
    ]
  };
  
  const pool = messages[resident.id] || ['...'];
  return pool[Math.floor(Math.random() * pool.length)];
}

// 检查是否启用了AI居民模式
function isAIRresidentMode() {
  return localStorage.getItem('blxst_ai_resident_mode') === 'true';
}

// 启用/停用AI居民模式
function toggleAIRresidentMode() {
  const current = isAIRresidentMode();
  localStorage.setItem('blxst_ai_resident_mode', !current);
  return !current;
}

// 导出给全局使用
window.AIResidents = {
  getCurrent: getCurrentAIRresident,
  setCurrent: setCurrentAIRresident,
  getAll: getAllAIRResidents,
  format: formatAIRresident,
  generateMessage: generateAIRresidentMessage,
  isMode: isAIRresidentMode,
  toggle: toggleAIRresidentMode,
  RESIDENTS: AI_RESIDENTS
};
