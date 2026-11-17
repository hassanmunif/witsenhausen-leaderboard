# Third-party assets

These files are copied unchanged from their npm packages so the site works
without a CDN. `scripts/build_site.py` copies this folder to `site/vendor/`.

| Folder | Package | Version | Licence |
|---|---|---|---|
| `katex/` | [katex](https://www.npmjs.com/package/katex): `katex.min.js`, `katex.min.css`, `contrib/auto-render.min.js` and the `.woff2` fonts | 0.19.1 | MIT (code), SIL OFL 1.1 (fonts); see `katex/LICENSE` |
| `latin-modern/` | Latin Modern Roman web fonts, taken from [latex.css](https://www.npmjs.com/package/latex.css) | 1.14.0 | GUST Font Licence (legally identical to the LPPL) |

To update KaTeX, replace the files in `katex/` with those from a newer
`katex/dist/` (only the `.woff2` fonts are needed).
