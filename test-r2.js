export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // Test R2 access
    try {
      const object = await env.BUCKET.get("logo/blxst-logo.png");
      if (object) {
        return new Response("R2 works! Got: " + object.key, {
          headers: { "Content-Type": "text/plain" }
        });
      }
      return new Response("Object not found", { status: 404 });
    } catch (e) {
      return new Response("Error: " + e.message, { status: 500 });
    }
  }
}
