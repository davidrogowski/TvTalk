// Redirects the legacy *.workers.dev hostname to the canonical tvtalk.fun
// domain (preserving path + query so shared links keep working), and serves
// the static site for every other host via the ASSETS binding.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.hostname.endsWith(".workers.dev")) {
      url.hostname = "tvtalk.fun";
      url.port = "";
      return Response.redirect(url.toString(), 301);
    }
    return env.ASSETS.fetch(request);
  },
};
