export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  url.pathname = '/human';
  return env.ASSETS.fetch(new Request(url, request));
}
