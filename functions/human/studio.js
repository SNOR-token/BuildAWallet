export async function onRequest(context) {
  const url = new URL(context.request.url);
  url.pathname = "/human-studio.html";
  return context.env.ASSETS.fetch(new Request(url.toString(), context.request));
}
