"""Lead Dashboard — Web UI wrapping the channel-tools MCP servers.

Runs as a standalone FastAPI server. Calls the MCP servers internally
to provide company search, lead scoring, and enrichment via a clean UI.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
import httpx
import os
import re

app = FastAPI(title="Lead Dashboard")

templates = Jinja2Templates(directory="templates")

# ── API Keys ──────────────────────────────────────────────
APOLLO_KEY = os.environ.get("APOLLO_API_KEY", "vp42h07NcldZU1xA1769TA")


# ── Models ────────────────────────────────────────────────
class SearchRequest(BaseModel):
    industry: Optional[str] = None
    min_employees: Optional[int] = None
    max_employees: Optional[int] = None
    location: Optional[str] = None
    keywords: Optional[str] = None
    limit: Optional[int] = 10


class QualifyRequest(BaseModel):
    company: str
    domain: Optional[str] = None


class EnrichRequest(BaseModel):
    domain: Optional[str] = None
    company: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────
def _html_escape(text: str) -> str:
    """Escape text for safe HTML rendering."""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))


async def _apollo_post(endpoint: str, payload: dict) -> dict | None:
    url = f"https://api.apollo.io/v1/{endpoint}"
    headers = {"Content-Type": "application/json", "x-api-key": APOLLO_KEY}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            return None
        return resp.json()


# ── Routes ────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/search-companies")
async def api_search_companies(req: SearchRequest):
    payload = {"page": 1, "per_page": min(req.limit or 10, 25)}
    if req.industry:
        payload["q_organization_industry_tags"] = [req.industry]
    if req.keywords:
        payload["q_keywords"] = req.keywords
    if req.location:
        payload["q_organization_location"] = req.location
    if req.min_employees or req.max_employees:
        r = {}
        if req.min_employees: r["min"] = req.min_employees
        if req.max_employees: r["max"] = req.max_employees
        payload["organization_num_employees_ranges"] = [str(r)]

    data = await _apollo_post("mixed_companies/search", payload)
    if not data:
        return JSONResponse({"error": "Apollo API error — check your API key and plan."})

    orgs = data.get("organizations", [])
    if not orgs:
        return JSONResponse({"html": "<div style='color: var(--text-dim); text-align: center; padding: 40px;'>No companies found matching those criteria.</div>"})

    total = data.get("total_entries", len(orgs))
    cards = []
    for org in orgs[:10]:
        name = _html_escape(org.get("name", "?"))
        domain = _html_escape(org.get("primary_domain", "") or "")
        desc = _html_escape((org.get("short_description", "") or "")[:150])
        emp = org.get("estimated_num_employees", "?")
        ind = _html_escape(", ".join(org.get("industry_tags", [])[:3]) or "?")
        rev = org.get("estimated_revenue", {})
        rev_str = f"${rev['value']:,.0f}" if isinstance(rev, dict) and rev.get("value") else "N/A"
        tech = org.get("technology_names", [])[:5]
        tech_html = "".join(f'<span class="tag">{_html_escape(t)}</span>' for t in tech) if tech else ""

        cards.append(f"""
        <div class="result-card">
            <div style="display:flex;justify-content:space-between;align-items:start">
                <div>
                    <h3>{name}</h3>
                    <div class="meta">{domain} · 👥 {emp} · 💰 {rev_str}</div>
                </div>
                <div><span class="tag">{ind}</span></div>
            </div>
            <div class="meta" style="margin-top:6px">{desc}</div>
            <div class="tags">{tech_html}</div>
        </div>""")

    html = f'<div style="font-size:13px;color:var(--text-dim);margin-bottom:12px">Found {total} companies — showing top {len(orgs)}</div>' + "".join(cards)
    return JSONResponse({"html": html})


@app.post("/api/qualify-lead")
async def api_qualify_lead(req: QualifyRequest):
    domain = req.domain or ""

    if not domain:
        data = await _apollo_post("organizations/search", {
            "q_organization_name": req.company, "per_page": 1
        })
        if data and data.get("organizations"):
            domain = data["organizations"][0].get("primary_domain", "")

    if not domain:
        return JSONResponse({"html": "<div style='color:var(--text-dim);padding:40px;text-align:center'>Could not find domain for this company.</div>"})

    data = await _apollo_post("organizations/search", {
        "q_organization_domains": [domain], "per_page": 1
    })
    if not data or not data.get("organizations"):
        return JSONResponse({"html": f"<pre>No data found for {_html_escape(req.company)}</pre>"})

    org = data["organizations"][0]
    name = _html_escape(org.get("name", req.company))
    domain = _html_escape(domain)

    # Scoring
    score = 10
    reasons = [[40, "Base score: 10"]]
    emp = org.get("estimated_num_employees", 0) or 0
    if emp >= 200: score += 25; reasons.append([25, f"Enterprise ({emp} employees)"])
    elif emp >= 50: score += 15; reasons.append([15, f"Mid-market ({emp} employees)"])
    elif emp >= 10: score += 10; reasons.append([10, f"SMB ({emp} employees)"])

    rev = org.get("estimated_revenue", {})
    if isinstance(rev, dict) and rev.get("value"):
        score += 15; reasons.append([15, f"Revenue ${rev['value']:,.0f}"])

    ind_text = " ".join(org.get("industry_tags", [])).lower()
    if any(w in ind_text for w in ["software", "information technology", "saas", "cyber"]):
        score += 10; reasons.append([10, "Tech/SaaS industry"])

    if org.get("linkedin_url"): score += 5; reasons.append([5, "Active LinkedIn"])
    tech = org.get("technology_names", []) or []
    if tech: score += 10; reasons.append([10, f"{len(tech)} technologies"])
    keywords = org.get("keywords", []) or []
    if any("partn" in k.lower() or "channel" in k.lower() or "reseller" in k.lower() for k in keywords):
        score += 10; reasons.append([10, "Channel keywords found"])
    if org.get("funding_events"): score += 10; reasons.append([10, "Venture-backed"])

    score = min(score, 100)
    tier_class = "score-hot" if score >= 75 else "score-warm" if score >= 50 else "score-cool"
    tier_label = "🔥 HOT" if score >= 75 else "✅ WARM" if score >= 50 else "🟡 COOL"
    color = "var(--green)" if score >= 75 else "var(--yellow)" if score >= 50 else "var(--red)"

    bars = "".join(f'<div style="display:flex;justify-content:space-between;font-size:13px;margin:4px 0"><span>{_html_escape(r[1])}</span><span style="color:var(--text-dim)">+{r[0]}</span></div>' for r in reasons[1:])

    ind_tags = _html_escape(", ".join(org.get("industry_tags", [])[:4]) or "?")
    tech_html = ", ".join(org.get("technology_names", [])[:8]) if tech else "?"
    linkedin = org.get("linkedin_url", "N/A")

    html = f"""
    <div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <h3 style="font-size:18px">{name}</h3>
            <span class="score-badge {tier_class}">{tier_label} {score}/100</span>
        </div>
        <div class="meta" style="margin-bottom:16px">{domain}</div>
        <div class="score-bar"><div class="score-fill" style="width:{score}%;background:{color}"></div></div>

        <div style="margin-top:16px">
            <div style="font-size:13px;font-weight:500;margin-bottom:8px">Scoring Breakdown</div>
            {bars}
        </div>

        <div style="margin-top:16px;display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px">
            <div><span style="color:var(--text-dim)">Industry:</span> {ind_tags}</div>
            <div><span style="color:var(--text-dim)">Employees:</span> {emp}</div>
            <div style="grid-column:1/-1"><span style="color:var(--text-dim)">Tech Stack:</span> {_html_escape(tech_html)}</div>
            <div style="grid-column:1/-1"><span style="color:var(--text-dim)">LinkedIn:</span> <a href="{_html_escape(linkedin)}" style="color:var(--accent)" target="_blank">{_html_escape(linkedin)}</a></div>
        </div>
    </div>"""
    return JSONResponse({"html": html})


@app.post("/api/enrich-company")
async def api_enrich_company(req: EnrichRequest):
    payload = {"per_page": 1}
    if req.domain: payload["q_organization_domains"] = [req.domain]
    elif req.company: payload["q_organization_name"] = req.company
    else: return JSONResponse({"html": "<pre>Provide a domain or company name.</pre>"})

    data = await _apollo_post("organizations/search", payload)
    if not data or not data.get("organizations"):
        return JSONResponse({"html": "<pre>No company found.</pre>"})

    org = data["organizations"][0]
    name = _html_escape(org.get("name", "N/A"))
    domain = _html_escape(org.get("primary_domain", "N/A"))
    emp = org.get("estimated_num_employees", "?")
    rev = org.get("estimated_revenue", {})
    rev_str = f"${rev['value']:,.0f}" if isinstance(rev, dict) and rev.get("value") else "N/A"
    year = org.get("founded_year", "?")
    ind = _html_escape(", ".join(org.get("industry_tags", [])[:5]) or "?")
    funding = len(org.get("funding_events", []))
    tech = _html_escape(", ".join(org.get("technology_names", [])[:10]) or "?")
    kw = _html_escape(", ".join(org.get("keywords", [])[:10]) or "?")
    linkedin = org.get("linkedin_url", "N/A")
    desc = _html_escape((org.get("short_description", "") or "")[:400])

    html = f"""
    <div>
        <h3 style="font-size:18px;margin-bottom:4px">{name}</h3>
        <div class="meta" style="margin-bottom:16px">{domain}</div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:13px">
            <div><span style="color:var(--text-dim)">👥 Employees:</span> {emp}</div>
            <div><span style="color:var(--text-dim)">💰 Revenue:</span> {rev_str}</div>
            <div><span style="color:var(--text-dim)">📅 Founded:</span> {year}</div>
            <div><span style="color:var(--text-dim)">💵 Funding:</span> {funding} rounds</div>
            <div style="grid-column:1/-1"><span style="color:var(--text-dim)">🏷️ Industry:</span> {ind}</div>
            <div style="grid-column:1/-1"><span style="color:var(--text-dim)">🔧 Tech Stack:</span> {tech}</div>
            <div style="grid-column:1/-1"><span style="color:var(--text-dim)">🔑 Keywords:</span> {kw}</div>
            <div style="grid-column:1/-1"><span style="color:var(--text-dim)">🔗 LinkedIn:</span> <a href="{_html_escape(linkedin)}" style="color:var(--accent)" target="_blank">{_html_escape(linkedin)}</a></div>
            <div style="grid-column:1/-1;margin-top:8px;line-height:1.5">{desc}</div>
        </div>
    </div>"""
    return JSONResponse({"html": html})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)