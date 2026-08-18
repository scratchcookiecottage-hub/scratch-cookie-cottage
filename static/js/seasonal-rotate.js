(function () {
  var roots = document.querySelectorAll("[data-rotate]");
  roots.forEach(function (root) {
    var frames = root.querySelectorAll("img");
    if (frames.length < 2) return;
    var i = 0;
    setInterval(function () {
      frames[i].classList.remove("is-on");
      i = (i + 1) % frames.length;
      frames[i].classList.add("is-on");
    }, 3200);
  });
})();
