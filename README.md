# NocoDB TLS & Vulnerability Scanner

A lightweight, containerized security scanner that acts as a bridge between **NocoDB** and **testssl.sh**.

This image automates the process of fetching domains from a NocoDB table, scanning them for SSL/TLS vulnerabilities using `testssl.sh`, and writing the results (Grades, Vulnerabilities, Dates) back to NocoDB. It is designed to be orchestrated by **Kestra**, but can run in any Docker environment.

## Features

- **Automated Fetching:** Pulls target domains from NocoDB based on an "Active" checkbox.
- **Deep Scanning:** Uses the industry-standard `testssl.sh` for cipher, protocol, and vulnerability checks.
- **Smart Reporting:** Updates NocoDB with the SSL Grade (e.g., A+, F), finding details, and the last scan timestamp.
- **Stateless:** Designed to run as a short-lived container (perfect for Cron jobs or Kestra flows).

---

## 1. NocoDB Setup (Prerequisites)

Before running the container, you need a table in NocoDB to hold your assets.

1. Create a new Table (e.g., named `Domains`).
2. Create the following columns with these **exact names** (case-sensitive):

    - **Domain** (Type: SingleLineText) -> *The URL to scan (e.g., google.com)*
    - **Active** (Type: Checkbox) -> *Only rows with this checked will be scanned*
    - **SSL_Grade** (Type: SingleLineText) -> *Stores the result (A+, B, F, etc.)*
    - **Vulnerabilities** (Type: LongText) -> *Stores error details or critical findings*
    - **Last_Scan_Date** (Type: DateTime) -> *Stores when the scan happened*
    - **Id** (Type: Integer) -> *System default column, usually already exists*

3. Generate an API Token in NocoDB (Settings -> Tokens).
4. Note down your `Table ID` (found in the URL when viewing the table).

---

## 2. Usage with Kestra (Recommended)

The best way to use this image is via a scheduled Kestra Flow. This ensures the container runs periodically and cleans up afterwards.

**Kestra Flow Example:**

    id: tls-scanner-job
    namespace: security.ops
    
    inputs:
      - id: nocodb_url
        type: STRING
        # If running locally, use host.docker.internal to reach the host
        defaults: "http://host.docker.internal:8080" 
        
      - id: nocodb_token
        type: STRING
        defaults: "YOUR_NOCODB_API_TOKEN"
        
      - id: table_id
        type: STRING
        defaults: "YOUR_TABLE_ID"
    
    tasks:
      - id: run-scanner
        type: io.kestra.plugin.docker.Run
        containerImage: bytenoise/tls-scanner:latest
        pullPolicy: ALWAYS
        
        # 'host: true' is often required if NocoDB runs on the same machine
        host: true 
        
        # Inject configuration via Environment Variables
        env:
          NOCODB_URL: "{{ inputs.nocodb_url }}"
          NOCODB_TOKEN: "{{ inputs.nocodb_token }}"
          TABLE_ID: "{{ inputs.table_id }}"
    
    triggers:
      - id: weekly-schedule
        type: io.kestra.core.models.triggers.types.Schedule
        cron: "0 3 * * 0" # Runs every Sunday at 03:00 AM

---

## 3. Usage with Docker CLI (Manual)

You can also run the scanner manually for debugging purposes.

    docker run --rm \
      --network host \
      -e NOCODB_URL="http://localhost:8080" \
      -e NOCODB_TOKEN="your-token" \
      -e TABLE_ID="your-table-id" \
      bytenoise/tls-scanner:latest

---

## Environment Variables

| Variable | Description | Required |
| :--- | :--- | :--- |
| `NOCODB_URL` | The full URL to your NocoDB instance (e.g. `http://192.168.1.5:8080`). | Yes |
| `NOCODB_TOKEN` | Your NocoDB API Token (`xc-token`). | Yes |
| `TABLE_ID` | The ID of the table containing the domains. | Yes |
| `TESTSSL_PATH` | Path to testssl.sh script (default: `/opt/testssl.sh/testssl.sh`). | No |

## Networking Note

If you are running Kestra or this container inside Docker, and your NocoDB is also running in Docker (or on the Host), **do not use `localhost`** in the `NOCODB_URL`. 

- Use `http://host.docker.internal:8080` (Docker Desktop / standard setups).
- Or use the actual LAN IP address of your server.
- Or place both containers in the same Docker Network.
- 
