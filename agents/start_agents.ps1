# Starts AgentReady, the Tester and the Fixer in mailbox mode (connected to Agentverse / ASI:One),
# each in its own PowerShell window, so they keep running when other apps close.
#   powershell -ExecutionPolicy Bypass -File agents\start_agents.ps1
$dir = $PSScriptRoot
$python = Join-Path $dir ".venv\Scripts\python.exe"
$agents = @(
    @{ Title = "AgentReady"; Script = "agentready_agent\agent.py" },
    @{ Title = "AgentReady Tester"; Script = "tester_agent\agent.py" },
    @{ Title = "AgentReady Fixer"; Script = "fixer_agent\agent.py" }
)
foreach ($a in $agents) {
    $cmd = "`$Host.UI.RawUI.WindowTitle = '$($a.Title)'; `$env:AGENT_MAILBOX = 'true'; Set-Location '$dir'; & '$python' '$($a.Script)'"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd
}
Write-Host "Started: AgentReady (8001), Tester (8002), Fixer (8003). Close a window to stop that agent."
