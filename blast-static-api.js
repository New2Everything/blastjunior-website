// blast-static-api - R2公开访问Worker
// 提供 /public/* 路径访问R2中的公开文件

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    let path = url.pathname;

    // 处理 /public/* 路径
    if (path.startsWith('/public/')) {
      // 处理URL编码的括号等特殊字符
      path = decodeURIComponent(path.replace('/public/', ''));
      return serveR2(env, path);
    }

    // 处理根路径，直接重定向到首页
    if (path === '/' || path === '') {
      return new Response('', {
        status: 302,
        headers: { 'Location': '/' }
      });
    }

    return new Response('Not Found', { status: 404 });
  }
};

async function serveR2(env, key) {
  try {
    const object = await env.BUCKET.get(key);
    
    if (!object) {
      return new Response('File not found', { status: 404 });
    }

    const contentType = getContentType(key);
    
    return new Response(object.body, {
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=86400',
        'Access-Control-Allow-Origin': '*'
      }
    });
  } catch (e) {
    return new Response('Error: ' + e.message, { status: 500 });
  }
}

function getContentType(key) {
  const ext = key.split('.').pop()?.toLowerCase();
  const types = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'webp': 'image/webp',
    'svg': 'image/svg+xml',
    'mp4': 'video/mp4',
    'webm': 'video/webm',
    'mp3': 'audio/mpeg',
    'wav': 'audio/wav',
    'json': 'application/json',
    'js': 'application/javascript',
    'css': 'text/css',
    'html': 'text/html',
    'txt': 'text/plain'
  };
  return types[ext] || 'application/octet-stream';
}
