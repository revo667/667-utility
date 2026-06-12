DEV_PROGRAMS = {

"Visual Studio Code": "Microsoft.VisualStudioCode",
"GitHub Desktop": "GitHub.GitHubDesktop",
"Python": "Python.Python.3.13"

}


BASIC_APPS = {

"Steam": "Valve.Steam",
"Discord": "Discord.DiscordDesktop",
"Spotify": "SpotifyAB.SpotifyMusic",
"Chrome": "Google.Chrome",
"Brave": "BraveSoftware.BraveBrowser"

}

TOOLS = {

"Notepad++": "Notepad++.Notepad++",
"7-Zip": "7-Zip.7-Zip",
"Lightshot": "Lightshot.Lightshot",
"NVCleanstall": "TechPowerUp.NVCleanstall"

}

def list_devprograms():
    for name, winget_id in DEV_PROGRAMS.items():
        print(f"{name:<25} | {winget_id}")

def list_tools():
    for name, winget_id in TOOLS.items():
        print(f"{name} | {winget_id}")

def list_basicapps():
    for name, winget_id in BASIC_APPS.items():
        print(f"{name} | {winget_id}")