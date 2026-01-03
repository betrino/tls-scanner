import requests
import subprocess
import json
import os
import datetime
import sys

# --- KONFIGURATION AUS UMGEBUNGSVARIABLEN ---
# Wir lesen die Werte nun aus dem Environment. 
# Der zweite Wert ist jeweils ein Fallback (optional, hier 'None' um Fehler zu erzwingen).
NOCODB_URL = os.getenv("NOCODB_URL")
NOCODB_TOKEN = os.getenv("NOCODB_TOKEN")
TABLE_ID = os.getenv("TABLE_ID")
# Standard-Pfad im Docker Container, kann bei Bedarf überschrieben werden
TESTSSL_PATH = os.getenv("TESTSSL_PATH", "/opt/testssl.sh/testssl.sh") 

# --- VALIDIERUNG ---
# Verhindert, dass das Skript läuft, wenn wichtige Config fehlt
if not all([NOCODB_URL, NOCODB_TOKEN, TABLE_ID]):
    print("CRITICAL ERROR: Missing environment variables.")
    print(f"NOCODB_URL: {'OK' if NOCODB_URL else 'MISSING'}")
    print(f"NOCODB_TOKEN: {'OK' if NOCODB_TOKEN else 'MISSING'}")
    print(f"TABLE_ID: {'OK' if TABLE_ID else 'MISSING'}")
    sys.exit(1)

# API Header für NocoDB
HEADERS = {
    "xc-token": NOCODB_TOKEN,
    "Content-Type": "application/json"
}

def get_active_domains():
    """Holt alle Domains, bei denen 'Active' = true ist."""
    print("Fetching domains from NocoDB...")
    try:
        # Filterung: (Active,is,true) - Syntax kann je nach NocoDB Version variieren, 
        # hier holen wir erst alles und filtern in Python für Robustheit.
        url = f"{NOCODB_URL}/api/v2/tables/{TABLE_ID}/records"
        params = {"limit": 100, "offset": 0} 
        
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        
        data = response.json()
        records = data.get('list', [])
        
        # Filtern nach Active Checkbox (NocoDB gibt oft true/false oder 1/0 zurück)
        active_domains = [r for r in records if r.get('Active')]
        print(f"Found {len(active_domains)} active domains to scan.")
        return active_domains
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        sys.exit(1)

def run_testssl(domain):
    """Führt testssl.sh aus und gibt den Grade und Findings zurück."""
    print(f"--- Scanning: {domain} ---")
    
    # Temporärer Output-Dateiname
    json_file = f"temp_{domain}.json"
    
    # Command: --jsonfile erzeugt strukturierten Output. --fast für schnelleren Test (optional entfernen)
    # Wir nutzen hier Standard-Scan, kann aber 5+ Minuten dauern pro Domain!
    cmd = [
        "/bin/bash", TESTSSL_PATH,
        "--jsonfile", json_file,
        "--quiet", "--warnings", "off",
        domain
    ]
    
    scan_date = datetime.datetime.now().isoformat()
    grade = "ERR"
    details = ""

    try:
        # Timeout setzen, damit sich das Skript nicht aufhängt (z.B. 10 Minuten)
        subprocess.run(cmd, timeout=600, check=False) # check=False, da testssl auch bei Vulns non-zero exit code haben kann
        
        if os.path.exists(json_file):
            with open(json_file, 'r') as f:
                scan_results = json.load(f)
            
            # Parsing: Wir suchen nach der ID "overall_grade"
            # testssl.sh JSON ist eine Liste von Objekten
            grade_obj = next((item for item in scan_results if item.get("id") == "overall_grade"), None)
            
            if grade_obj:
                grade = grade_obj.get("finding", "Unknown")
            else:
                grade = "Unknown"
            
            # Optional: Kritische Vulns sammeln (Beispiel)
            vulns = [item['id'] for item in scan_results if item.get('severity') in ['HIGH', 'CRITICAL']]
            if vulns:
                details = f"Detected High/Crit Issues: {', '.join(vulns)}"
            else:
                details = "No HIGH/CRITICAL severities detected."

            # Cleanup
            os.remove(json_file)
        else:
            details = "Error: JSON output file was not generated. Domain unreachable?"
            
    except subprocess.TimeoutExpired:
        details = "Timeout: Scan took too long."
        print("Scan timed out.")
    except Exception as e:
        details = f"Script Error: {str(e)}"
        print(f"Error executing testssl: {e}")

    return grade, details, scan_date

def update_nocodb(record_id, grade, details, scan_date):
    """Aktualisiert den Datensatz in NocoDB."""
    url = f"{NOCODB_URL}/api/v2/tables/{TABLE_ID}/records"
    
    payload = {
        "Id": record_id, # ID ist zwingend für Update
        "SSL_Grade": grade,
        "Vulnerabilities": details,
        "Last_Scan_Date": scan_date
    }
    
    try:
        response = requests.patch(url, headers=HEADERS, json=payload)
        response.raise_for_status()
        print(f"Successfully updated record {record_id} with Grade {grade}")
    except Exception as e:
        print(f"Failed to update NocoDB: {e}")

def main():
    domains = get_active_domains()
    
    for record in domains:
        domain_name = record.get('Domain')
        record_id = record.get('Id')
        
        if not domain_name:
            continue
            
        grade, details, scan_date = run_testssl(domain_name)
        update_nocodb(record_id, grade, details, scan_date)

if __name__ == "__main__":
    main()
  
