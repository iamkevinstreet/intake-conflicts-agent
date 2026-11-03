########################################################################
#                                                                      #
#            backend/src/intake_agent/dashboard/__init__.py            #
#                                                                      #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-11-03
Last modified on:  2026-11-03

The evaluation dashboard: compare runs and see which scenarios did not
end as expected, and how much work each one took.

Run it with `python -m intake_agent.dashboard`. The modules: data (run
files to tables, which the Tableau export shares), views (what the
dashboard shows from those tables), theme, the charts (verdict_chart,
steps_chart, run_charts), tiles, layout, page, app, and export (the
figures the case study draws). Nothing is imported here, so reading
the tables does not load Dash.
"""
