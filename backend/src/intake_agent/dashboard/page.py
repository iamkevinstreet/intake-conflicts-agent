########################################################################
#                                                                      #
#              backend/src/intake_agent/dashboard/page.py              #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

Sets the HTML page Dash serves the app in: the fonts, and the colours
and styles in light and dark. Dash fills the placeholders in braces
with its metas, title, styles, config and scripts. The styles carry the
kevindstreet.com tokens; the charts take the same colours from
theme.py.
"""

########################################################################
#                                                                      #
#                               Imports                                #
#                                                                      #
########################################################################
# Standard library
from __future__ import annotations

from typing import Final

# Third-party
from kds.logs import get_logger

########################################################################
#                                                                      #
#                           Global constants                           #
#                                                                      #
########################################################################
log = get_logger(__name__)

########################################################################
#                                                                      #
#                           Local constants                            #
#                                                                      #
########################################################################
# log.debug("Sets the address of the Geist fonts, both families in one request")
FONTS_URL: Final = (
    "https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600"
    "&family=Geist+Mono:wght@400;500&display=swap"
)
# log.debug("Sets the page's head up to its styles: Dash's placeholders and the fonts")
HEAD: Final = (
    '<!DOCTYPE html>\n<html lang="en"><head>{%metas%}<title>{%title%}</title>{%favicon%}\n'
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    f'<link href="{FONTS_URL}" rel="stylesheet">\n'
    "{%css%}\n"
)
# log.debug("Sets the styles: the tokens in light and dark, then each part of the page")
STYLE: Final = """<style>
  :root {
    color-scheme: light dark;
    --ground: #f5f5f2; --surface: #ffffff; --surface-2: #ecece8;
    --ink: #111214; --ink-2: #585d66; --ink-3: #868c96;
    --line: rgba(17,18,20,0.1); --line-2: rgba(17,18,20,0.18);
    --line-strong: rgba(17,18,20,0.92);
    --mark: #ffe45c; --pass: #13794a; --miss: #b5641a;
    --run-0: #111214; --run-1: #80868f; --run-2: #a7acb4;
    --shadow: 0 1px 2px rgba(17,18,20,0.06), 0 12px 40px -12px rgba(17,18,20,0.18);
    --font: Geist, 'Geist Variable', ui-sans-serif, system-ui, 'Helvetica Neue', Arial, sans-serif;
    --mono: 'Geist Mono', ui-monospace, Menlo, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --ground: #0a0b0e; --surface: #121419; --surface-2: #1a1d24;
      --ink: #f2f3f5; --ink-2: #9aa1ac; --ink-3: #6e7581;
      --line: rgba(255,255,255,0.08); --line-2: rgba(255,255,255,0.16);
      --line-strong: rgba(255,255,255,0.92);
      --mark: #f3cf4a; --pass: #5dd39e; --miss: #f0b14c;
      --run-0: #f2f3f5; --run-1: #7d8490; --run-2: #4a505b;
      --shadow: 0 1px 2px rgba(0,0,0,0.5), 0 24px 60px -20px rgba(0,0,0,0.7);
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--ground); color: var(--ink); font-family: var(--font);
    font-size: 15px; line-height: 1.55; -webkit-font-smoothing: antialiased; }
  .wrap { max-width: 76rem; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }
  .eyebrow { margin: 0 0 0.5rem; font-family: var(--mono); font-size: 0.75rem;
    letter-spacing: 0.04em; text-transform: uppercase; color: var(--ink-3); }
  h1, h2, h3 { font-weight: 500; letter-spacing: -0.022em; margin: 0; }
  h1 { font-size: 2.6rem; line-height: 1.05; }
  h2 { font-size: 1.4rem; margin: 3rem 0 0.75rem; }
  h3 { font-size: 0.95rem; letter-spacing: -0.01em; margin: 0 0 0.5rem; }
  .lede { color: var(--ink-2); max-width: 44rem; margin: 0.75rem 0 1.5rem; }
  ::selection { background: var(--mark); color: #111214; }
  .controls { display: grid; gap: 0.4rem; max-width: 40rem; margin-bottom: 1rem; }
  .controls label { font-size: 0.8rem; font-weight: 500; color: var(--ink-3); }
  .legend { display: flex; flex-wrap: wrap; gap: 0.5rem 1.25rem; margin: 0 0 1.25rem;
    font-size: 0.85rem; color: var(--ink-2); }
  .key { display: inline-flex; align-items: center; gap: 0.5rem; }
  .dot { width: 10px; height: 10px; border-radius: 50%; }
  .dot.run-0 { background: var(--run-0); } .dot.run-1 { background: var(--run-1); }
  .dot.run-2 { background: var(--run-2); }
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(10.5rem, 1fr)); gap: 1px;
    background: var(--line); border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
    margin-bottom: 1.25rem; }
  .tile { background: var(--surface); padding: 1rem 1.1rem 1.1rem; display: grid;
    align-content: start; gap: 0.2rem; }
  .tile-value { font-size: 1.9rem; font-weight: 500; letter-spacing: -0.03em; line-height: 1.1; }
  .tile-label { font-size: 0.8rem; color: var(--ink-2); line-height: 1.35; }
  .tile-delta { margin-top: 0.35rem; font-size: 0.75rem; font-weight: 500; display: inline-flex;
    gap: 0.35rem; align-items: center; color: var(--ink-3); }
  .tile-delta.good { color: var(--pass); } .tile-delta.bad { color: var(--miss); }
  .tile-delta .arrow { width: 0; height: 0; border-left: 4px solid transparent;
    border-right: 4px solid transparent; }
  .tile-delta .arrow.up { border-bottom: 6px solid currentColor; }
  .tile-delta .arrow.down { border-top: 6px solid currentColor; }
  .tile-delta .arrow.no { width: 8px; height: 2px; border: 0; background: currentColor; }
  .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
  .card { background: var(--surface); border: 1px solid var(--line); border-radius: 14px;
    padding: 1rem 1.1rem 0.75rem; box-shadow: var(--shadow); min-width: 0; }
  .card.wide { grid-column: 1 / -1; }
  @media (max-width: 52rem) {
    .grid { grid-template-columns: minmax(0, 1fr); } h1 { font-size: 2rem; }
  }
  /* Dash's own widgets in the same skin. Dash 4 themes its components through these
     variables; they are set on body so they also reach menus that open outside the
     app's container. */
  body {
    --Dash-Fill-Inverse-Strong: var(--surface);
    --Dash-Fill-Interactive-Strong: var(--ink);
    --Dash-Fill-Interactive-Weak: var(--surface-2);
    --Dash-Fill-Primary-Hover: var(--surface-2);
    --Dash-Fill-Primary-Active: var(--surface-2);
    --Dash-Fill-Disabled: var(--surface-2);
    --Dash-Stroke-Strong: var(--line-2);
    --Dash-Stroke-Weak: var(--line);
    --Dash-Text-Primary: var(--ink);
    --Dash-Text-Strong: var(--ink);
    --Dash-Text-Weak: var(--ink-2);
    --Dash-Text-Disabled: var(--ink-3);
    --Dash-Shading-Strong: rgba(0, 0, 0, 0.35);
    --Dash-Shading-Weak: rgba(0, 0, 0, 0.2);
  }
  .dash-dropdown, .dash-dropdown-options { font-family: var(--font); font-size: 14px;
    border-radius: 10px; }
  .dash-dropdown { min-height: 2.75rem; background: var(--surface);
    border: 1px solid var(--line-2); }
  .dash-dropdown-value-item { background: var(--surface-2); border-radius: 999px;
    padding: 0.1rem 0.6rem; }
  .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner td,
  .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner th {
    font-family: var(--font) !important; }
  .dash-table-container { border-top: 1px solid var(--line-strong); }
  .previous-next-container, .page-number { color: var(--ink-2); font-family: var(--font); }
  .previous-next-container button { background: var(--surface); color: var(--ink);
    border: 1px solid var(--line-2); border-radius: 999px; }
</style></head>
"""
# log.debug("Sets the body, where Dash puts the app, its config and its scripts")
BODY: Final = "<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"
# log.debug("Sets the whole page")
INDEX: Final = HEAD + STYLE + BODY
