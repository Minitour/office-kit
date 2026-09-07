/*
 * Progressive enhancement for the document. The page is fully readable with
 * JavaScript disabled — nothing here is required for content or layout.
 *
 * Placeholder scope: brand-mark cleanup and TOC current-section highlighting.
 * Delete what the document does not need.
 */

(() => {
  "use strict";

  const root = document.documentElement;

  /*
   * Brand logo. The mark is painted by CSS from --doc-logo, which points at
   * the shared brand directory. When it is set to `none` (or the variable is
   * missing entirely), drop the element rather than leave an empty slot in the
   * header.
   */
  const brandMark = document.querySelector(".brand-mark");
  if (brandMark) {
    const logo = getComputedStyle(root).getPropertyValue("--doc-logo").trim();
    if (logo === "" || logo === "none") {
      brandMark.remove();
    }
  }

  /*
   * Mark the table-of-contents entry for the section currently in view.
   * Skipped when the reader prefers reduced motion or IntersectionObserver is
   * unavailable.
   */
  const tocLinks = Array.from(document.querySelectorAll(".doc-toc a[href^='#']"));
  if (tocLinks.length > 0 && "IntersectionObserver" in window) {
    const byId = new Map(
      tocLinks.map((link) => [link.getAttribute("href").slice(1), link]),
    );

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const link = byId.get(entry.target.id);
          if (!link) continue;
          if (entry.isIntersecting) {
            link.setAttribute("aria-current", "true");
          } else {
            link.removeAttribute("aria-current");
          }
        }
      },
      { rootMargin: "-40% 0px -55% 0px" },
    );

    for (const id of byId.keys()) {
      const section = document.getElementById(id);
      if (section) observer.observe(section);
    }
  }
})();
