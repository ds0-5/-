// web/auth.js
// 作用：自动给所有请求带上通行证（token），没登录就跳登录页
// 用法：在每个页面的 <head> 里加一行 <script src="auth.js"></script>

(function () {
  // 1) 拦下原始的 fetch
  const _fetch = window.fetch.bind(window);

  // 2) 换上一个「会自动加 token」的版本
  window.fetch = function (url, options) {
    options = options || {};
    const token = localStorage.getItem("yinku_token") || "";
    if (token) {
      options.headers = Object.assign({}, options.headers, {
        Authorization: "Bearer " + token,
      });
    }
    return _fetch(url, options).then(function (resp) {
      // 3) 服务器说「未登录」（401），就跳回登录页
      if (resp.status === 401) {
        localStorage.removeItem("yinku_token");
        location.href = "login.html";
      }
      return resp;
    });
  };
})();
