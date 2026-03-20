import os
import msal
import requests
from dotenv import load_dotenv
load_dotenv()  # leser .env i prosjektroten

# Sett hvilke delte postbokser du vil teste
MAILBOXES = [
    "Salg@arcticmotor.no",
    "service@arcticmotor.no",
]

TENANT_ID = os.environ["GRAPH_TENANT_ID"]
CLIENT_ID = os.environ["GRAPH_CLIENT_ID"]
CLIENT_SECRET = os.environ["GRAPH_CLIENT_SECRET"]

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["https://graph.microsoft.com/.default"]
BASE_URL = "https://graph.microsoft.com/v1.0"


def get_access_token() -> str:
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=SCOPE)
    if "access_token" not in result:
        raise RuntimeError(f"Kunne ikke hente token: {result}")
    return result["access_token"]


def get_latest_message(mailbox: str):
    token = get_access_token()

    url = f"{BASE_URL}/users/{mailbox}/mailFolders/Inbox/messages"
    params = {
        "$top": 1,
        "$orderby": "receivedDateTime desc",
    }

    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )
    print("Status:", resp.status_code)
    data = resp.json()
    print("Response JSON:", data)

    if resp.status_code == 200 and "value" in data and data["value"]:
        msg = data["value"][0]
        print("\nSiste melding:")
        print("Subject:", msg.get("subject"))
        print("From:", msg.get("from"))
        print("Received:", msg.get("receivedDateTime"))
    else:
        print("\nFant ingen meldinger eller fikk ikke forventet struktur.")


if __name__ == "__main__":
    for mailbox in MAILBOXES:
        print("\n=== Tester mailbox:", mailbox, "===")
        try:
            get_latest_message(mailbox)
        except Exception as exc:
            print("Feil for", mailbox, ":", exc)