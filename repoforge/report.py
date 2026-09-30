"""Standalone, escaped HTML run report; no network assets or scripts."""
from html import escape


def render_report(report: dict) -> str:
    cards = []
    for event in report["events"]:
        if event["stage"] != "test":
            continue
        result = event["payload"]
        passed = result["passed"]
        cards.append(
            '<article><div class="row"><h2>' +
            ("Baseline" if result["attempt"] == 0 else f'Repair {result["attempt"]}') +
            '</h2><span class="badge ' + ("pass" if passed else "fail") + '">' +
            ("PASS" if passed else "FAIL") + '</span></div><pre>' +
            escape(result["log"]) + '</pre></article>'
        )
    return '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RepoForge | Run evidence</title><style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#10151f;color:#e6edf5}
body{max-width:1180px;margin:0 auto;padding:48px 24px}header{border-top:3px solid #5ee6b0;padding-top:22px}
.eyebrow{letter-spacing:3px;color:#5ee6b0;font-size:13px}h1{font-size:clamp(34px,5vw,62px);letter-spacing:-2px;margin:16px 0}
.lede{color:#a7b6cb;font-size:19px;max-width:760px;line-height:1.6}.metrics{display:flex;gap:18px;flex-wrap:wrap;margin:32px 0}
.metric{background:#1a2332;padding:20px 24px;border:1px solid #2a384c;border-radius:12px;flex:1;min-width:180px}
.metric strong{display:block;font-size:24px;margin-bottom:8px}.metric span,footer{color:#a7b6cb;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:18px}
article{background:#161f2c;border:1px solid #2a384c;border-radius:12px;overflow:hidden}
.row{display:flex;justify-content:space-between;align-items:center;padding:12px 20px;border-bottom:1px solid #2a384c}
h2{font-size:18px}.badge{font-size:12px;font-weight:700;padding:6px 10px;border-radius:30px}
.pass{color:#5ee6b0;background:#153e35}.fail{color:#ffc480;background:#443222}
pre{font-size:12px;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere;padding:18px;color:#b9c8db;max-height:440px;overflow:auto}
footer{margin-top:28px;line-height:1.8}code{color:#5ee6b0}</style>
<header><div class="eyebrow">REPOFORGE / ENGINEERING EVIDENCE</div><h1>A repair is only a hypothesis.</h1>
<p class="lede">Follow the test feedback from a failing baseline to a reviewable patch. Every attempt is recorded; passing tests remain a reason to review, not a reason to skip review.</p></header>
<div class="metrics"><div class="metric"><strong>''' + escape(report["status"]) + '''</strong><span>Final workflow state</span></div>
<div class="metric"><strong>''' + str(report["attempts"]) + '''</strong><span>Repair attempts</span></div>
<div class="metric"><strong>''' + escape(report["runner"]) + '''</strong><span>Execution mode</span></div></div>
<div class="grid">''' + "".join(cards) + '''</div><footer>Provider: <code>''' + escape(report["provider"]) + '''</code> · Run: <code>''' + escape(report["run_id"]) + '''</code><br>
DemoProvider is a deterministic synthetic demonstration, not model-generated code. Live model quality is not measured here.</footer></html>'''
