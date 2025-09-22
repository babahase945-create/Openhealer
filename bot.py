import os
import time
from github import Github, Auth

# ==============================================================================
# KONFIGURATION
# ==============================================================================

# Holt den GitHub Token. Versucht zuerst den Standardnamen 'GITHUB_TOKEN',
# dann als Fallback den Namen 'TOKEN', um Fehler zu vermeiden.
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN') or os.getenv('TOKEN')

# Deine persönliche Spenden-Nachricht.
SPENDEN_NACHRICHT = """
*This pull request was generated automatically by the CodeHealer bot.*
*My purpose is to help keep open-source projects secure by fixing known vulnerabilities.*
*If you found this contribution helpful, please consider supporting my ongoing maintenance and server costs via Litecoin (LTC):*

*ltc1qx5ri6dqss6w56ktw9rgx4zghrjgwatfnw7lf4p*
"""

# ==============================================================================
# BOT-LOGIK
# ==============================================================================

def finde_unsichere_projekte(github_client):
    """Sucht auf GitHub nach Python-Projekten, die potenziell unsicher sind."""
    print("INFO: Starte Suche nach verwundbaren Python-Projekten...")
    # Schließt archivierte Projekte von vornherein aus, um Fehler zu vermeiden.
    query = 'filename:requirements.txt language:python pushed:<2024-01-01 archived:false'
    
    try:
        results = github_client.search_repositories(query=query)
        print(f"INFO: {results.totalCount} aktive, potenzielle Projekte gefunden. Analysiere die ersten...")
        return results
    except Exception as e:
        print(f"FEHLER bei der Projektsuche: {e}")
        return []

def analysiere_projekt_und_erstelle_fix(repo):
    """
    Analysiert die Abhängigkeiten eines Projekts und generiert einen Fix.
    """
    # Doppelte Absicherung: Überspringe archivierte Projekte.
    if repo.archived:
        print(f"INFO: Projekt '{repo.full_name}' ist archiviert. Überspringe.")
        return {"hat_luecke": False}

    try:
        print(f"INFO: Analysiere Projekt '{repo.full_name}'...")
        requirements_file = repo.get_contents("requirements.txt")
        veraltete_requirements = requirements_file.decoded_content.decode("utf-8")
        
        if "requests==2.25.0" in veraltete_requirements:
            print(f"INFO: Sicherheitslücke in 'requests==2.25.0' in '{repo.full_name}' gefunden!")
            gefixte_requirements = veraltete_requirements.replace("requests==2.25.0", "requests==2.31.0")
            
            return {
                "hat_luecke": True,
                "repo_objekt": repo,
                "dateipfad": requirements_file.path,
                "sha": requirements_file.sha,
                "neuer_inhalt": gefixte_requirements,
                "luecke_beschreibung": "Sicherheitslücke in 'requests' < 2.31.0 (CVE-2023-32681) behoben."
            }
        else:
            print(f"INFO: Keine der gesuchten Lücken in '{repo.full_name}' gefunden.")
            return {"hat_luecke": False}
    except Exception as e:
        print(f"FEHLER bei der Analyse von '{repo.full_name}': {e}")
        return {"hat_luecke": False}

def erstelle_pull_request(fix_details):
    """Erstellt einen echten Pull Request auf GitHub, um den Fix vorzuschlagen."""
    repo = fix_details["repo_objekt"]
    try:
        print(f"AKTION: Erstelle Pull Request für '{repo.full_name}'...")
        
        source_branch = repo.get_branch(repo.default_branch)
        new_branch_name = f"codehealer-fix-{int(time.time())}"
        repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=source_branch.commit.sha)
        
        commit_message = f"Security: Fix für Schwachstelle in 'requests'"
        repo.update_file(
            path=fix_details["dateipfad"],
            message=commit_message,
            content=fix_details["neuer_inhalt"],
            sha=fix_details["sha"],
            branch=new_branch_name
        )
        
        pr_titel = f"CodeHealer Bot: Fix für Sicherheitslücke in 'requests'"
        pr_beschreibung = f"""
Hallo,

mein automatisierter Scan hat eine Sicherheitslücke in Ihren Projektabhängigkeiten gefunden.

**Details:**
{fix_details['luecke_beschreibung']}

Dieser Pull Request aktualisiert die `requests`-Bibliothek auf eine sichere Version. Es wird empfohlen, diesen Fix zu übernehmen, um die Sicherheit Ihres Projekts zu gewährleisten.

---
{SPENDEN_NACHRICHT}
"""
        pr = repo.create_pull(
            title=pr_titel,
            body=pr_beschreibung,
            head=new_branch_name,
            base=repo.default_branch
        )
        print(f"ERFOLG: Pull Request erfolgreich erstellt! URL: {pr.html_url}")
        
    except Exception as e:
        # Intelligente Fehlerbehandlung für gesperrte Projekte
        if "403 Forbidden" in str(e):
            print(f"WARNUNG: Projekt '{repo.full_name}' ist gesperrt (403 Forbidden). Ignoriere und mache weiter.")
        else:
            print(f"FEHLER beim Erstellen des Pull Requests für '{repo.full_name}': {e}")

# ==============================================================================
# HAUPTSCHLEIFE DES BOTS
# ==============================================================================
def main():
    print("+++ Open-Source-Healer-Bot wird gestartet +++")
    
    if not GITHUB_TOKEN:
        print("FEHLER: GITHUB_TOKEN oder TOKEN wurde nicht in den Secrets gefunden. Bot wird beendet.")
        return
        
    auth = Auth.Token(GITHUB_TOKEN)
    g = Github(auth=auth)
    
    print("INFO: Authentifizierung erfolgreich. Starte Hauptschleife...")
    
    while True:
        try:
            projekte = finde_unsichere_projekte(g)
            
            aktionen_in_diesem_lauf = 0
            for projekt in projekte:
                if aktionen_in_diesem_lauf >= 5:
                    print("INFO: Aktionslimit für diesen Lauf erreicht.")
                    break
                    
                fix = analysiere_projekt_und_erstelle_fix(projekt)
                if fix["hat_luecke"]:
                    erstelle_pull_request(fix)
                    aktionen_in_diesem_lauf += 1
                    print("INFO: Warte 60 Sekunden bis zur nächsten Aktion...")
                    time.sleep(60) 
            
            print("\nINFO: Zyklus abgeschlossen. Warte 1 Stunde bis zum nächsten globalen Scan.")
            time.sleep(3600)
        except Exception as e:
            print(f"FATALER FEHLER in der Hauptschleife: {e}")
            print("INFO: Warte 10 Minuten vor Neustart des Zyklus...")
            time.sleep(600)

if __name__ == "__main__":
    main()
          
