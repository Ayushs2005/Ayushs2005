# Dynamic GitHub Activity & Profile Signal Telemetry Generator for PowerShell
param (
    [string]$Username = "Ayushs2005",
    [string]$Token = $env:GITHUB_TOKEN
)

$headers = @{
    "User-Agent" = "GitHub-Activity-Telemetry-Sync"
    "Accept" = "application/vnd.github.v3+json"
}
if ($Token) {
    $headers["Authorization"] = "Bearer $Token"
}

Write-Host "Fetching GitHub statistics for @$Username..."

# 1. Fetch contribution years
$yearsQuery = @"
query {
  user(login: "$Username") {
    contributionsCollection {
      contributionYears
    }
  }
}
"@

$yearsRes = Invoke-RestMethod -Uri "https://api.github.com/graphql" -Method Post -Headers $headers -Body (@{ query = $yearsQuery } | ConvertTo-Json)
$years = $yearsRes.data.user.contributionsCollection.contributionYears

$totalCommits = 0
$totalPRs = 0
$totalContributions = 0

foreach ($y in $years) {
    $from = "$y-01-01T00:00:00Z"
    $to = "$y-12-31T23:59:59Z"
    $yearQuery = @"
query {
  user(login: "$Username") {
    contributionsCollection(from: "$from", to: "$to") {
      totalCommitContributions
      restrictedContributionsCount
      totalPullRequestContributions
      contributionCalendar {
        totalContributions
      }
    }
  }
}
"@
    $resY = Invoke-RestMethod -Uri "https://api.github.com/graphql" -Method Post -Headers $headers -Body (@{ query = $yearQuery } | ConvertTo-Json)
    $cc = $resY.data.user.contributionsCollection
    $commits = $cc.totalCommitContributions + $cc.restrictedContributionsCount
    $totalCommits += $commits
    $totalPRs += $cc.totalPullRequestContributions
    $totalContributions += $cc.contributionCalendar.totalContributions
}

# 2. Fetch Repositories, Stars & Languages
$reposQuery = @"
query {
  user(login: "$Username") {
    repositories(first: 100, ownerAffiliations: OWNER) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
            }
          }
        }
      }
    }
  }
}
"@

$reposRes = Invoke-RestMethod -Uri "https://api.github.com/graphql" -Method Post -Headers $headers -Body (@{ query = $reposQuery } | ConvertTo-Json)
$repoNodes = $reposRes.data.user.repositories.nodes
$reposCount = $reposRes.data.user.repositories.totalCount

$totalStars = 0
$languages = @{}

foreach ($repo in $repoNodes) {
    $totalStars += $repo.stargazerCount
    if ($repo.languages -and $repo.languages.edges) {
        foreach ($edge in $repo.languages.edges) {
            $langName = $edge.node.name
            $size = $edge.size
            if ($languages.ContainsKey($langName)) {
                $languages[$langName] += [long]$size
            } else {
                $languages[$langName] = [long]$size
            }
        }
    }
}

$commitsDisplay = [Math]::Max($totalCommits, $totalContributions)
$commitsPlus = if ($commitsDisplay -ge 10) { "+" } else { "" }
$prsDisplay = $totalPRs
$prsPlus = if ($prsDisplay -ge 5) { "+" } else { "" }

Write-Host "Stats:"
Write-Host "  Stars: $totalStars"
Write-Host "  Lifetime Commits / Contribs: $commitsDisplay"
Write-Host "  Pull Requests: $prsDisplay"
Write-Host "  Repositories: $reposCount"

# Language Breakdown Calculations
$totalBytes = 0
foreach ($val in $languages.Values) { $totalBytes += $val }
if ($totalBytes -eq 0) { $totalBytes = 1 }

$sortedKeys = $languages.Keys | Sort-Object { $languages[$_] } -Descending
$top4Keys = $sortedKeys | Select-Object -First 4
$otherKeys = $sortedKeys | Select-Object -Skip 4

$otherBytes = 0
foreach ($k in $otherKeys) { $otherBytes += $languages[$k] }

$palette = @(
    @{ dot = "#e62842"; text = "#ff7084"; bar = "#e62842" },
    @{ dot = "#f5a623"; text = "#ffd580"; bar = "#f5a623" },
    @{ dot = "#e06843"; text = "#ffaa88"; bar = "#e06843" },
    @{ dot = "#48c774"; text = "#a3f0bd"; bar = "#48c774" },
    @{ dot = "#7a88b8"; text = "#c4cce8"; bar = "#7a88b8" }
)

$langLines = @()
$idx = 0

foreach ($k in $top4Keys) {
    $bytes = $languages[$k]
    $pct = [Math]::Round(($bytes / $totalBytes) * 100, 1)
    $pctStr = "{0:N1}%" -f $pct
    $barW = [Math]::Max([int][Math]::Round(($pct / 100.0) * 380), 4)
    $yOff = $idx * 32
    $c = $palette[$idx]
    $safeName = [System.Security.SecurityElement]::Escape($k)
    
    $langLines += @"
      <!-- $($idx + 1). $safeName -->
      <g transform="translate(0, $yOff)">
        <circle cx="4" cy="7" r="3.5" fill="$($c.dot)" />
        <text x="14" y="11" fill="#ffffff" font-size="11.5" font-weight="700" class="mono">$safeName</text>
        <text x="380" y="11" fill="$($c.text)" font-size="11.5" font-weight="700" class="mono" text-anchor="end">$pctStr</text>
        <rect x="0" y="17" width="380" height="7" rx="3.5" fill="#18070a" stroke="#3a0f16" stroke-width="1" />
        <rect x="0" y="17" width="$barW" height="7" rx="3.5" fill="$($c.bar)" />
      </g>
"@
    $idx++
}

if ($otherBytes -gt 0) {
    $otherPct = [Math]::Round(($otherBytes / $totalBytes) * 100, 1)
    $otherPctStr = "{0:N1}%" -f $otherPct
    $otherBarW = [Math]::Max([int][Math]::Round(($otherPct / 100.0) * 380), 4)
    $yOff = $idx * 32
    $c = $palette[4]
    
    $langLines += @"
      <!-- $($idx + 1). Others -->
      <g transform="translate(0, $yOff)">
        <circle cx="4" cy="7" r="3.5" fill="$($c.dot)" />
        <text x="14" y="11" fill="#ffffff" font-size="11.5" font-weight="700" class="mono">Others</text>
        <text x="380" y="11" fill="$($c.text)" font-size="11.5" font-weight="700" class="mono" text-anchor="end">$otherPctStr</text>
        <rect x="0" y="17" width="380" height="7" rx="3.5" fill="#18070a" stroke="#3a0f16" stroke-width="1" />
        <rect x="0" y="17" width="$otherBarW" height="7" rx="3.5" fill="$($c.bar)" />
      </g>
"@
}

$renderedLangs = $langLines -join "`n`n"

$commitsTspan = if ($commitsPlus) { "<tspan font-size=""14"" fill=""#e62842"">$commitsPlus</tspan>" } else { "" }
$prsTspan = if ($prsPlus) { "<tspan font-size=""14"" fill=""#48c774"">$prsPlus</tspan>" } else { "" }

$svgContent = @"
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 850 260" width="100%" height="100%">
  <defs>
    <linearGradient id="actFullBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#080406" />
      <stop offset="50%" stop-color="#120508" />
      <stop offset="100%" stop-color="#060204" />
    </linearGradient>
    <linearGradient id="actBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#660000" />
      <stop offset="50%" stop-color="#8b111a" stop-opacity="0.6" />
      <stop offset="100%" stop-color="#2b0204" />
    </linearGradient>
    <style>
      .mono { font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; }
      .sans { font-family: 'Inter', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; }
      @keyframes actPulse {
        0%, 100% { fill: #8b111a; opacity: 0.6; }
        50% { fill: #e62842; opacity: 1; }
      }
      .act-dot { animation: actPulse 2s infinite; }
    </style>
  </defs>

  <!-- Container -->
  <rect width="850" height="260" rx="10" fill="url(#actFullBg)" />
  <rect x="1" y="1" width="848" height="258" rx="9" fill="none" stroke="url(#actBorder)" stroke-width="1.2" />

  <!-- LEFT HALF: GITHUB ACTIVITY & PROFILE SIGNAL -->
  <g transform="translate(24, 24)">
    <!-- Header -->
    <circle cx="4" cy="4" r="4" class="act-dot" />
    <text x="16" y="8" fill="#ffffff" font-size="12" font-weight="700" class="mono" letter-spacing="0.12em">ACTIVITY &amp; PROFILE SIGNAL</text>
    <text x="385" y="8" fill="#e62842" font-size="10.5" font-weight="700" class="mono" text-anchor="end">@$Username</text>
    <line x1="0" y1="20" x2="385" y2="20" stroke="#380a0f" stroke-width="1" />

    <!-- 4 Metrics Cells -->
    <g transform="translate(0, 32)">
      <!-- Stars -->
      <g transform="translate(0, 0)">
        <rect width="90" height="64" rx="6" fill="#140608" stroke="#4a0404" stroke-width="1" />
        <text x="10" y="18" fill="#a89a9c" font-size="9" font-weight="700" class="mono">STARS</text>
        <text x="10" y="46" fill="#ffffff" font-size="22" font-weight="900" class="sans">$totalStars</text>
        <text x="68" y="46" fill="#f5a623" font-size="13">&#9733;</text>
      </g>

      <!-- Commits -->
      <g transform="translate(98, 0)">
        <rect width="90" height="64" rx="6" fill="#140608" stroke="#4a0404" stroke-width="1" />
        <text x="10" y="18" fill="#a89a9c" font-size="9" font-weight="700" class="mono">COMMITS</text>
        <text x="10" y="46" fill="#ffffff" font-size="22" font-weight="900" class="sans">$commitsDisplay$commitsTspan</text>
        <text x="70" y="46" fill="#e62842" font-size="13">&#9889;</text>
      </g>

      <!-- Pull Requests -->
      <g transform="translate(196, 0)">
        <rect width="90" height="64" rx="6" fill="#140608" stroke="#4a0404" stroke-width="1" />
        <text x="10" y="18" fill="#a89a9c" font-size="9" font-weight="700" class="mono">PULL REQS</text>
        <text x="10" y="46" fill="#ffffff" font-size="22" font-weight="900" class="sans">$prsDisplay$prsTspan</text>
        <text x="70" y="46" fill="#48c774" font-size="13">&#8645;</text>
      </g>

      <!-- Repos -->
      <g transform="translate(294, 0)">
        <rect width="90" height="64" rx="6" fill="#140608" stroke="#4a0404" stroke-width="1" />
        <text x="10" y="18" fill="#a89a9c" font-size="9" font-weight="700" class="mono">REPOSITORIES</text>
        <text x="10" y="46" fill="#ffffff" font-size="22" font-weight="900" class="sans">$reposCount</text>
        <text x="68" y="46" fill="#7a88b8" font-size="13">&#128230;</text>
      </g>
    </g>

    <!-- Profile Assessment Banner (A+ Grade) -->
    <g transform="translate(0, 108)">
      <rect width="385" height="82" rx="6" fill="#160609" stroke="#660000" stroke-width="1" />
      <!-- Big A+ Badge -->
      <g transform="translate(42, 41)">
        <circle cx="0" cy="0" r="28" fill="#0a0204" stroke="#e62842" stroke-width="1.5" />
        <text x="-3" y="11" fill="#ffffff" font-size="30" font-weight="900" class="sans" text-anchor="middle">A<tspan font-size="20" fill="#e62842" dx="1" dy="-6">+</tspan></text>
      </g>
      <!-- Telemetry text -->
      <g transform="translate(85, 24)">
        <text x="0" y="0" fill="#ffffff" font-size="11.5" font-weight="700" class="mono">ENGINEERING PROFILE SIGNAL</text>
        <text x="0" y="18" fill="#e62842" font-size="10" font-weight="700" class="mono">VERIFIED SDET &amp; CLOUD ARCHITECTURE</text>
        <text x="0" y="34" fill="#a8898c" font-size="9.5" class="mono">99.4% Test Automation &#183; Cloud Certified (AZ-104)</text>
      </g>
    </g>
  </g>

  <!-- VERTICAL DIVIDER -->
  <line x1="425" y1="20" x2="425" y2="240" stroke="#33080c" stroke-width="1.2" stroke-dasharray="4 3" />

  <!-- RIGHT HALF: HIGH CONTRAST LANGUAGE COMPOSITION -->
  <g transform="translate(445, 24)">
    <!-- Header -->
    <circle cx="4" cy="4" r="4" fill="#f5a623" />
    <text x="16" y="8" fill="#ffffff" font-size="12" font-weight="700" class="mono" letter-spacing="0.12em">LANGUAGE COMPOSITION</text>
    <text x="380" y="8" fill="#8f7c7f" font-size="10" class="mono" text-anchor="end">CODEBASE RATIO</text>
    <line x1="0" y1="20" x2="380" y2="20" stroke="#380a0f" stroke-width="1" />

    <!-- Language Progress Bars -->
    <g transform="translate(0, 32)">
$renderedLangs
    </g>
  </g>
</svg>
"@

$targetPath = Join-Path (Get-Location) "Assets\activity-telemetry-full.svg"
[System.IO.File]::WriteAllText($targetPath, $svgContent, [System.Text.Encoding]::UTF8)
Write-Host "Successfully generated and updated $targetPath"
