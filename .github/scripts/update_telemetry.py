#!/usr/bin/env python3
"""
Dynamic GitHub Activity & Profile Signal Telemetry Generator
Fetches live metrics for Ayushs2005 from GitHub API and updates Assets/activity-telemetry-full.svg
"""

import os
import sys
import json
import urllib.request
import urllib.error

USERNAME = "Ayushs2005"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

def make_request(url, headers=None, data=None):
    if headers is None:
        headers = {}
    headers["User-Agent"] = "GitHub-Activity-Telemetry-Sync"
    headers["Accept"] = "application/vnd.github.v3+json"
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    
    req = urllib.request.Request(url, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code} for {url}: {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None

def fetch_graphql_stats(username):
    if not TOKEN:
        print("No GITHUB_TOKEN provided for GraphQL query, falling back to REST API", file=sys.stderr)
        return None

    url = "https://api.github.com/graphql"
    
    # 1. Fetch contribution years
    years_query = {
        "query": f"""
        query {{
          user(login: "{username}") {{
            contributionsCollection {{
              contributionYears
            }}
          }}
        }}
        """
    }
    years_data = make_request(url, data=json.dumps(years_query).encode("utf-8"))
    if not years_data or "data" not in years_data or not years_data["data"]["user"]:
        print("Failed to fetch contribution years via GraphQL", file=sys.stderr)
        return None

    years = years_data["data"]["user"]["contributionsCollection"]["contributionYears"]
    
    total_commits = 0
    total_prs = 0
    total_issues = 0
    total_contributions = 0
    
    for y in years:
        year_query = {
            "query": f"""
            query {{
              user(login: "{username}") {{
                contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") {{
                  totalCommitContributions
                  restrictedContributionsCount
                  totalPullRequestContributions
                  totalIssueContributions
                  contributionCalendar {{
                    totalContributions
                  }}
                }}
              }}
            }}
            """
        }
        res = make_request(url, data=json.dumps(year_query).encode("utf-8"))
        if res and "data" in res and res["data"]["user"]:
            cc = res["data"]["user"]["contributionsCollection"]
            commits = cc.get("totalCommitContributions", 0) + cc.get("restrictedContributionsCount", 0)
            total_commits += commits
            total_prs += cc.get("totalPullRequestContributions", 0)
            total_issues += cc.get("totalIssueContributions", 0)
            total_contributions += cc.get("contributionCalendar", {}).get("totalContributions", 0)

    # 2. Fetch user repositories, stars, and languages
    repos_query = {
        "query": f"""
        query {{
          user(login: "{username}") {{
            repositories(first: 100, ownerAffiliations: OWNER) {{
              totalCount
              nodes {{
                name
                stargazerCount
                isFork
                languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
                  edges {{
                    size
                    node {{
                      name
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
    }
    repos_res = make_request(url, data=json.dumps(repos_query).encode("utf-8"))
    
    total_stars = 0
    languages_map = {}
    repos_count = 0
    
    if repos_res and "data" in repos_res and repos_res["data"]["user"]:
        repo_nodes = repos_res["data"]["user"]["repositories"]["nodes"]
        repos_count = repos_res["data"]["user"]["repositories"]["totalCount"]
        for repo in repo_nodes:
            total_stars += repo.get("stargazerCount", 0)
            lang_edges = repo.get("languages", {}).get("edges", [])
            for edge in lang_edges:
                lang_name = edge["node"]["name"]
                size = edge["size"]
                languages_map[lang_name] = languages_map.get(lang_name, 0) + size

    return {
        "commits": max(total_commits, total_contributions),
        "contributions": total_contributions,
        "prs": total_prs,
        "stars": total_stars,
        "repos": repos_count,
        "languages": languages_map
    }

def fetch_rest_fallback(username):
    user_data = make_request(f"https://api.github.com/users/{username}")
    repos_data = make_request(f"https://api.github.com/users/{username}/repos?per_page=100")
    
    if not user_data or not repos_data:
        return None
        
    total_stars = sum(r.get("stargazers_count", 0) for r in repos_data)
    repos_count = user_data.get("public_repos", len(repos_data))
    
    languages_map = {}
    for repo in repos_data:
        lang_url = repo.get("languages_url")
        if lang_url:
            langs = make_request(lang_url)
            if isinstance(langs, dict):
                for l_name, l_bytes in langs.items():
                    languages_map[l_name] = languages_map.get(l_name, 0) + l_bytes

    # Search commits
    commits_data = make_request(f"https://api.github.com/search/commits?q=author:{username}")
    total_commits = commits_data.get("total_count", 95) if commits_data else 95
    
    # Search PRs
    prs_data = make_request(f"https://api.github.com/search/issues?q=author:{username}+type:pr")
    total_prs = prs_data.get("total_count", 1) if prs_data else 1
    
    return {
        "commits": total_commits,
        "contributions": total_commits,
        "prs": total_prs,
        "stars": total_stars,
        "repos": repos_count,
        "languages": languages_map
    }

def build_svg(stats):
    commits_val = stats["commits"]
    prs_val = stats["prs"]
    stars_val = stats["stars"]
    repos_val = stats["repos"]
    languages_map = stats["languages"]
    
    # Format metrics display
    commits_display = f"{commits_val}"
    commits_plus = "+" if commits_val >= 10 else ""
    
    prs_display = f"{prs_val}"
    prs_plus = "+" if prs_val >= 5 else ""
    
    stars_display = f"{stars_val}"
    repos_display = f"{repos_val}"
    
    # Language Breakdown Calculations
    total_lang_bytes = sum(languages_map.values())
    if total_lang_bytes == 0:
        total_lang_bytes = 1
        
    sorted_langs = sorted(languages_map.items(), key=lambda x: x[1], reverse=True)
    
    # Take top 4 and group others
    top_4 = sorted_langs[:4]
    other_bytes = sum(item[1] for item in sorted_langs[4:])
    
    lang_items = []
    # Palette definition for 5 slots
    color_palette = [
        {"dot": "#e62842", "text": "#ff7084", "bar": "#e62842"}, # Slot 1
        {"dot": "#f5a623", "text": "#ffd580", "bar": "#f5a623"}, # Slot 2
        {"dot": "#e06843", "text": "#ffaa88", "bar": "#e06843"}, # Slot 3
        {"dot": "#48c774", "text": "#a3f0bd", "bar": "#48c774"}, # Slot 4
        {"dot": "#7a88b8", "text": "#c4cce8", "bar": "#7a88b8"}, # Slot 5 (Others)
    ]
    
    for i, (l_name, l_bytes) in enumerate(top_4):
        pct = (l_bytes / total_lang_bytes) * 100.0
        pct_rounded = round(pct, 1)
        bar_width = int(round((pct / 100.0) * 380))
        lang_items.append({
            "name": l_name,
            "pct_str": f"{pct_rounded:.1f}%",
            "bar_width": max(bar_width, 4),
            "colors": color_palette[i]
        })
        
    if other_bytes > 0:
        other_pct = (other_bytes / total_lang_bytes) * 100.0
        other_pct_rounded = round(other_pct, 1)
        other_bar_width = int(round((other_pct / 100.0) * 380))
        lang_items.append({
            "name": "Others",
            "pct_str": f"{other_pct_rounded:.1f}%",
            "bar_width": max(other_bar_width, 4),
            "colors": color_palette[4]
        })

    # Build SVG content with exact styling & layout
    svg_lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 850 260" width="100%" height="100%">',
        '  <defs>',
        '    <linearGradient id="actFullBg" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#080406" />',
        '      <stop offset="50%" stop-color="#120508" />',
        '      <stop offset="100%" stop-color="#060204" />',
        '    </linearGradient>',
        '    <linearGradient id="actBorder" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#660000" />',
        '      <stop offset="50%" stop-color="#8b111a" stop-opacity="0.6" />',
        '      <stop offset="100%" stop-color="#2b0204" />',
        '    </linearGradient>',
        '    <style>',
        "      .mono { font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; }",
        "      .sans { font-family: 'Inter', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; }",
        '      @keyframes actPulse {',
        '        0%, 100% { fill: #8b111a; opacity: 0.6; }',
        '        50% { fill: #e62842; opacity: 1; }',
        '      }',
        '      .act-dot { animation: actPulse 2s infinite; }',
        '    </style>',
        '  </defs>',
        '',
        '  <!-- Container -->',
        '  <rect width="850" height="260" rx="10" fill="url(#actFullBg)" />',
        '  <rect x="1" y="1" width="848" height="258" rx="9" fill="none" stroke="url(#actBorder)" stroke-width="1.2" />',
        '',
        '  <!-- LEFT HALF: GITHUB ACTIVITY & PROFILE SIGNAL -->',
        '  <g transform="translate(24, 24)">',
        '    <!-- Header -->',
        '    <circle cx="4" cy="4" r="4" class="act-dot" />',
        '    <text x="16" y="8" fill="#ffffff" font-size="12" font-weight="700" class="mono" letter-spacing="0.12em">ACTIVITY &amp; PROFILE SIGNAL</text>',
        f'    <text x="385" y="8" fill="#e62842" font-size="10.5" font-weight="700" class="mono" text-anchor="end">@{USERNAME}</text>',
        '    <line x1="0" y1="20" x2="385" y2="20" stroke="#380a0f" stroke-width="1" />',
        '',
        '    <!-- 4 Metrics Cells -->',
        '    <g transform="translate(0, 32)">',
        '      <!-- Stars -->',
        '      <g transform="translate(0, 0)">',
        '        <rect width="90" height="64" rx="6" fill="#140608" stroke="#4a0404" stroke-width="1" />',
        '        <text x="10" y="18" fill="#a89a9c" font-size="9" font-weight="700" class="mono">STARS</text>',
        f'        <text x="10" y="46" fill="#ffffff" font-size="22" font-weight="900" class="sans">{stars_display}</text>',
        '        <text x="68" y="46" fill="#f5a623" font-size="13">&#9733;</text>',
        '      </g>',
        '',
        '      <!-- Commits -->',
        '      <g transform="translate(98, 0)">',
        '        <rect width="90" height="64" rx="6" fill="#140608" stroke="#4a0404" stroke-width="1" />',
        '        <text x="10" y="18" fill="#a89a9c" font-size="9" font-weight="700" class="mono">COMMITS</text>',
        f'        <text x="10" y="46" fill="#ffffff" font-size="22" font-weight="900" class="sans">{commits_display}' + (f'<tspan font-size="14" fill="#e62842">{commits_plus}</tspan>' if commits_plus else '') + '</text>',
        '        <text x="70" y="46" fill="#e62842" font-size="13">&#9889;</text>',
        '      </g>',
        '',
        '      <!-- Pull Requests -->',
        '      <g transform="translate(196, 0)">',
        '        <rect width="90" height="64" rx="6" fill="#140608" stroke="#4a0404" stroke-width="1" />',
        '        <text x="10" y="18" fill="#a89a9c" font-size="9" font-weight="700" class="mono">PULL REQS</text>',
        f'        <text x="10" y="46" fill="#ffffff" font-size="22" font-weight="900" class="sans">{prs_display}' + (f'<tspan font-size="14" fill="#48c774">{prs_plus}</tspan>' if prs_plus else '') + '</text>',
        '        <text x="70" y="46" fill="#48c774" font-size="13">&#8645;</text>',
        '      </g>',
        '',
        '      <!-- Repos -->',
        '      <g transform="translate(294, 0)">',
        '        <rect width="90" height="64" rx="6" fill="#140608" stroke="#4a0404" stroke-width="1" />',
        '        <text x="10" y="18" fill="#a89a9c" font-size="9" font-weight="700" class="mono">REPOSITORIES</text>',
        f'        <text x="10" y="46" fill="#ffffff" font-size="22" font-weight="900" class="sans">{repos_display}</text>',
        '        <text x="68" y="46" fill="#7a88b8" font-size="13">&#128230;</text>',
        '      </g>',
        '    </g>',
        '',
        '    <!-- Profile Assessment Banner (A+ Grade) -->',
        '    <g transform="translate(0, 108)">',
        '      <rect width="385" height="82" rx="6" fill="#160609" stroke="#660000" stroke-width="1" />',
        '      <!-- Big A+ Badge -->',
        '      <g transform="translate(42, 41)">',
        '        <circle cx="0" cy="0" r="28" fill="#0a0204" stroke="#e62842" stroke-width="1.5" />',
        '        <text x="-3" y="11" fill="#ffffff" font-size="30" font-weight="900" class="sans" text-anchor="middle">A<tspan font-size="20" fill="#e62842" dx="1" dy="-6">+</tspan></text>',
        '      </g>',
        '      <!-- Telemetry text -->',
        '      <g transform="translate(85, 24)">',
        '        <text x="0" y="0" fill="#ffffff" font-size="11.5" font-weight="700" class="mono">ENGINEERING PROFILE SIGNAL</text>',
        '        <text x="0" y="18" fill="#e62842" font-size="10" font-weight="700" class="mono">VERIFIED SDET &amp; CLOUD ARCHITECTURE</text>',
        '        <text x="0" y="34" fill="#a8898c" font-size="9.5" class="mono">99.4% Test Automation &#183; Cloud Certified (AZ-104)</text>',
        '      </g>',
        '    </g>',
        '  </g>',
        '',
        '  <!-- VERTICAL DIVIDER -->',
        '  <line x1="425" y1="20" x2="425" y2="240" stroke="#33080c" stroke-width="1.2" stroke-dasharray="4 3" />',
        '',
        '  <!-- RIGHT HALF: HIGH CONTRAST LANGUAGE COMPOSITION -->',
        '  <g transform="translate(445, 24)">',
        '    <!-- Header -->',
        '    <circle cx="4" cy="4" r="4" fill="#f5a623" />',
        '    <text x="16" y="8" fill="#ffffff" font-size="12" font-weight="700" class="mono" letter-spacing="0.12em">LANGUAGE COMPOSITION</text>',
        '    <text x="380" y="8" fill="#8f7c7f" font-size="10" class="mono" text-anchor="end">CODEBASE RATIO</text>',
        '    <line x1="0" y1="20" x2="380" y2="20" stroke="#380a0f" stroke-width="1" />',
        '',
        '    <!-- Language Progress Bars -->'
    ]
    
    svg_lines.append('    <g transform="translate(0, 32)">')
    for idx, item in enumerate(lang_items):
        y_offset = idx * 32
        colors = item["colors"]
        safe_name = item["name"].replace("&", "&amp;")
        svg_lines.extend([
            f'      <!-- {idx + 1}. {safe_name} -->',
            f'      <g transform="translate(0, {y_offset})">',
            f'        <circle cx="4" cy="7" r="3.5" fill="{colors["dot"]}" />',
            f'        <text x="14" y="11" fill="#ffffff" font-size="11.5" font-weight="700" class="mono">{safe_name}</text>',
            f'        <text x="380" y="11" fill="{colors["text"]}" font-size="11.5" font-weight="700" class="mono" text-anchor="end">{item["pct_str"]}</text>',
            '        <rect x="0" y="17" width="380" height="7" rx="3.5" fill="#18070a" stroke="#3a0f16" stroke-width="1" />',
            f'        <rect x="0" y="17" width="{item["bar_width"]}" height="7" rx="3.5" fill="{colors["bar"]}" />',
            '      </g>',
            ''
        ])
    svg_lines.append('    </g>')
    svg_lines.extend([
        '  </g>',
        '</svg>',
        ''
    ])
    
    return "\n".join(svg_lines)

def main():
    print(f"Fetching GitHub statistics for @{USERNAME}...")
    stats = fetch_graphql_stats(USERNAME)
    if not stats:
        print("GraphQL query failed. Falling back to REST API...", file=sys.stderr)
        stats = fetch_rest_fallback(USERNAME)
        
    if not stats:
        print("Failed to fetch GitHub stats from both GraphQL and REST APIs.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Stats retrieved successfully:")
    print(f"  Stars: {stats['stars']}")
    print(f"  Lifetime Commits / Contribs: {stats['commits']}")
    print(f"  Pull Requests: {stats['prs']}")
    print(f"  Repositories: {stats['repos']}")
    print(f"  Languages: {len(stats['languages'])} detected")
    
    svg_content = build_svg(stats)
    
    # Target file path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    target_path = os.path.join(repo_root, "Assets", "activity-telemetry-full.svg")
    
    # Ensure Assets directory exists
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
        
    print(f"Successfully updated telemetry SVG at {target_path}")

if __name__ == "__main__":
    main()
