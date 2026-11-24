// Loaded when rhinventory is embedded in herniarchiv.cz (see "Embedding" in README.md).
(function () {
    // Theme requested by the embedding page, applied before the page renders
    var theme = document.currentScript.dataset.theme;
    if (theme) document.documentElement.dataset.theme = theme;

    // The embedding page redirects these to rhinventory itself
    var filesUrl = new URL('../files/', document.currentScript.src).href;

    // Links to other sites and files replace the embedding page instead of loading inside the frame
    document.addEventListener('click', function (e) {
        var a = e.target instanceof Element ? e.target.closest('a[href]') : null;
        if (a && !a.target && /^https?:$/.test(a.protocol) && (a.origin !== location.origin || a.href.startsWith(filesUrl))) {
            a.target = '_top';
        }
    }, true);
})();
