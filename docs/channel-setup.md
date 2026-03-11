# Kommunikációs csatornák konfigurálása

A platform támogatja, hogy az ágensek ne csak a webes felületen, hanem külső üzenetküldő csatornákon (Microsoft Teams, WhatsApp) is kérdéseket tehessenek fel és válaszokat fogadjanak. Ez lehetővé teszi az aszinkron munkafolyamatokat — az ágens feltesz egy kérdést, és a válasz akár órákkal később is megérkezhet.

---

## 1. Áttekintés

| Csatorna | Provider | Használat |
|----------|----------|-----------|
| **web_ui** | Beépített | Alapértelmezett, mindig aktív. SSE-n keresztül jelenik meg a böngészőben. |
| **teams** | Microsoft Bot Framework | Adaptive Card-os kérdések Teams chatben. |
| **whatsapp** | Twilio | WhatsApp üzenetküldés Twilio API-n keresztül. |

A csatornák engedélyezése a `.env` fájlban történik. Minden csatorna a `web_ui` mellett működik — ha egy külső csatorna nem elérhető, a kérdés automatikusan a webes felületen is megjelenik (fallback).

---

## 2. Microsoft Teams

### 2.1 Bot regisztrálása az Azure-ban

1. **Azure Portal** megnyitása: https://portal.azure.com

2. **Bot létrehozása:**
   - Keresse meg: **Azure Bot** (vagy **Bot Services**)
   - Kattintson: **Create** → **Azure Bot**
   - Töltse ki:
     - **Bot handle**: tetszőleges egyedi név (pl. `agent-platform-bot`)
     - **Subscription**: válassza ki az Azure előfizetését
     - **Resource Group**: válasszon meglévőt vagy hozzon létre újat
     - **Pricing tier**: **F0 (Free)** elegendő fejlesztéshez
     - **Microsoft App ID**: válassza a **"Create new Microsoft App ID"** opciót
   - Kattintson: **Create**

3. **App ID és Password lekérése:**
   - A bot létrehozása után nyissa meg a bot erőforrást
   - Navigáljon: **Configuration** → **Microsoft App ID**
   - Jegyezze fel az **App ID**-t (ez lesz a `APP_TEAMS_APP_ID`)
   - Kattintson: **"Manage Password"** → ez átviszi az **App Registrations** oldalra
   - Navigáljon: **Certificates & secrets** → **Client secrets** → **New client secret**
   - Adjon nevet (pl. `agent-platform`) és válasszon lejáratot
   - **Másolja ki az értéket** (Value) — ez lesz a `APP_TEAMS_APP_PASSWORD`
   - **Figyelem:** a secret csak egyszer jelenik meg, utána nem kérhető le újra!

4. **Messaging endpoint beállítása:**
   - Bot erőforrás → **Configuration**
   - **Messaging endpoint**: `https://<your-domain>/api/channels/teams/webhook`
   - Ha lokálisan fejleszt, használjon **ngrok**-ot vagy hasonló tunneling megoldást:
     ```bash
     ngrok http 8000
     # Másolja ki a https URL-t és adja hozzá: /api/channels/teams/webhook
     ```

5. **Teams csatorna engedélyezése:**
   - Bot erőforrás → **Channels**
   - Kattintson: **Microsoft Teams** → **Apply**
   - Fogadja el a szolgáltatási feltételeket

### 2.2 Conversation ID beszerzése

A `APP_TEAMS_DEFAULT_CONVERSATION_ID` szükséges a proaktív üzenetküldéshez (amikor a bot kezdeményezi a beszélgetést).

**Módszer 1 — Bot Framework Emulator:**
1. Töltse le a [Bot Framework Emulator](https://github.com/microsoft/BotFramework-Emulator/releases)-t
2. Csatlakozzon a bot-hoz
3. Az Emulator log-jában keresse a `conversation.id` mezőt

**Módszer 2 — Teams chatből:**
1. Írjon egy üzenetet a botnak Teams-ben
2. A webhook bejövő adatai között keresse a `conversation.id` mezőt
3. A backend logban megjelenik (debug módban): keresse a `teams_new_message` log bejegyzést

**Módszer 3 — Graph API:**
Ha már van Teams alkalmazás, a [Microsoft Graph API](https://learn.microsoft.com/en-us/graph/api/resources/conversation) segítségével is lekérdezhető.

### 2.3 Környezeti változók

Adja hozzá a `.env` fájlhoz:

```env
APP_TEAMS_ENABLED=true
APP_TEAMS_APP_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
APP_TEAMS_APP_PASSWORD=your-client-secret-value
APP_TEAMS_DEFAULT_CONVERSATION_ID=19:xxxxx@thread.v2
```

| Változó | Leírás | Kötelező |
|---------|--------|----------|
| `APP_TEAMS_ENABLED` | Csatorna engedélyezése (`true`/`false`) | Igen |
| `APP_TEAMS_APP_ID` | Azure Bot App ID (GUID) | Igen |
| `APP_TEAMS_APP_PASSWORD` | Azure App Registration client secret | Igen |
| `APP_TEAMS_SERVICE_URL` | Bot Framework service URL | Nem (default: `https://smba.trafficmanager.net/emea/`) |
| `APP_TEAMS_DEFAULT_CONVERSATION_ID` | Alapértelmezett Teams conversation a proaktív üzenetekhez | Ajánlott |

### 2.4 Service URL régiók

A `APP_TEAMS_SERVICE_URL` értéke a Teams régiójától függ:

| Régió | URL |
|-------|-----|
| EMEA (Európa) | `https://smba.trafficmanager.net/emea/` |
| Americas | `https://smba.trafficmanager.net/amer/` |
| APAC | `https://smba.trafficmanager.net/apac/` |

Az esetek többségében az alapértelmezett EMEA URL megfelelő. Ha nem működik, ellenőrizze a bejövő webhook activity `serviceUrl` mezőjét.

---

## 3. WhatsApp (Twilio)

### 3.1 Twilio fiók létrehozása

1. **Regisztráció:** https://www.twilio.com/try-twilio
   - Hozzon létre egy ingyenes fiókot
   - Erősítse meg az e-mail címét és telefonszámát

2. **Account SID és Auth Token lekérése:**
   - Bejelentkezés után: https://console.twilio.com
   - A **Dashboard** főoldalán azonnal látható:
     - **Account SID** — ez lesz a `APP_WHATSAPP_ACCOUNT_SID`
     - **Auth Token** — kattintson a szemre a megjelenítéshez, ez lesz a `APP_WHATSAPP_AUTH_TOKEN`

### 3.2 WhatsApp Sandbox beállítása (fejlesztéshez)

Éles WhatsApp Business számlához a Twilio WhatsApp Business API szükséges (lásd 3.3). Fejlesztéshez a **Sandbox** elegendő:

1. Navigáljon: **Messaging** → **Try it out** → **Send a WhatsApp message**
   - Vagy közvetlenül: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn

2. **Sandbox aktiválása:**
   - A Twilio ad egy sandbox telefonszámot (pl. `+14155238886`)
   - Ez lesz a `APP_WHATSAPP_FROM_NUMBER`
   - A telefonjáról küldjön egy WhatsApp üzenetet a megadott számra a megadott kóddal (pl. `join <sandbox-code>`)

3. **Webhook beállítása:**
   - A Sandbox beállításainál: **When a message comes in**
   - URL: `https://<your-domain>/api/channels/whatsapp/webhook`
   - Method: **POST**
   - Lokális fejlesztéshez használjon **ngrok**-ot:
     ```bash
     ngrok http 8000
     ```

### 3.3 Éles WhatsApp Business (production)

Éles használathoz:

1. **WhatsApp Business Profile** igénylése a Twilio-n:
   - https://www.twilio.com/docs/whatsapp/api
   - **Messaging** → **Senders** → **WhatsApp senders** → **Add new sender**
   - A Meta/Facebook üzleti verifikációs folyamaton kell átmenni (néhány nap)

2. **Saját telefonszám:**
   - Vásároljon egy Twilio telefonszámot: **Phone Numbers** → **Buy a Number**
   - Válasszon olyan számot, ami támogatja az SMS-t (WhatsApp is ezen keresztül megy)
   - Ezt a számot rendelje hozzá a WhatsApp sender-hez

3. **Webhook konfiguráció** megegyezik a sandbox-szal, de a sender beállításainál kell megadni.

### 3.4 Engedélyezett számok

Az `APP_WHATSAPP_ALLOWED_NUMBERS` biztonsági szűrő — csak ezekről a számokról fogad be üzeneteket. Ha üres, minden szám elfogadásra kerül (nem ajánlott éles környezetben).

Formátum: E.164 formátumú telefonszámok, vesszővel elválasztva.

### 3.5 Környezeti változók

Adja hozzá a `.env` fájlhoz:

```env
APP_WHATSAPP_ENABLED=true
APP_WHATSAPP_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
APP_WHATSAPP_AUTH_TOKEN=your-auth-token
APP_WHATSAPP_FROM_NUMBER=+14155238886
APP_WHATSAPP_ALLOWED_NUMBERS=["+36301234567","+36709876543"]
```

| Változó | Leírás | Kötelező |
|---------|--------|----------|
| `APP_WHATSAPP_ENABLED` | Csatorna engedélyezése (`true`/`false`) | Igen |
| `APP_WHATSAPP_ACCOUNT_SID` | Twilio Account SID (`AC` prefix) | Igen |
| `APP_WHATSAPP_AUTH_TOKEN` | Twilio Auth Token | Igen |
| `APP_WHATSAPP_FROM_NUMBER` | Küldő szám (E.164 formátum) | Igen |
| `APP_WHATSAPP_ALLOWED_NUMBERS` | Engedélyezett fogadó számok JSON tömb | Ajánlott |

---

## 4. Működési elv

### 4.1 Kérdés küldése

Amikor egy ágens az `ask_user` eszközt használja és a feladathoz csatorna van rendelve:

```
Ágens → ask_user("Melyik verziót preferálod?")
    → InteractionBroker.create_interaction(channel="teams")
        → TeamsChannel.send_question()  → Adaptive Card a Teams chatben
        → WebUIChannel.send_question()  → SSE event a böngészőnek (fallback)
    → Várakozás válaszra (max 5 perc rövid timeout)
        → Ha nem jön válasz: AgentSuspended kivétel → feladat felfüggesztve
        → Ha jön válasz: ágens folytatja a munkát
```

### 4.2 Válasz fogadása

A válasz három úton érkezhet:

1. **Webes felület:** `POST /api/interactions/respond` — a felhasználó a böngészőben válaszol
2. **Teams webhook:** `POST /api/channels/teams/webhook` — a felhasználó a Teams-ben válaszol (szöveg vagy Adaptive Card gomb)
3. **WhatsApp webhook:** `POST /api/channels/whatsapp/webhook` — a felhasználó WhatsApp-on válaszol

Bármelyik útról is jön a válasz, az `InteractionBroker` gondoskodik a megfelelő ágens értesítéséről.

### 4.3 Felfüggesztés és folytatás

Külső csatornákon (Teams, WhatsApp) a válasz akár órákat is késhet. Ilyenkor:

1. Az ágens **felfüggesztődik** (`AgentSuspended` kivétel)
2. A feladat állapota `suspended` lesz
3. Az ADK session megőrzi a teljes beszélgetési kontextust
4. Amikor a válasz megérkezik, a `InteractionBroker` resume callback-je újraindítja az ágenst
5. Az ágens a session-ből visszatölti az állapotát és folytatja a munkát

---

## 5. Csatorna megadása feladatnál

A feladat beküldésekor a `channel` paraméterben adható meg, melyik csatornán kommunikáljon az ágens:

```json
POST /api/tasks/
{
    "task": "Generálj egy REST API-t a megadott specifikáció alapján",
    "channel": "teams"
}
```

Ha nincs megadva, az alapértelmezett csatorna a `web_ui`.

---

## 6. Hibaelhárítás

### Teams

| Probléma | Megoldás |
|----------|---------|
| Bot nem válaszol Teams-ben | Ellenőrizze, hogy a messaging endpoint helyes és elérhető kívülről (HTTPS szükséges) |
| 401 Unauthorized a webhook-on | Ellenőrizze az `APP_TEAMS_APP_ID` és `APP_TEAMS_APP_PASSWORD` értékeket |
| Üzenet nem érkezik meg | Ellenőrizze, hogy a Teams channel engedélyezve van a bot-on az Azure Portal-on |
| Token lekérés sikertelen | Ellenőrizze, hogy a client secret nem járt-e le |
| Rossz service URL | Ellenőrizze a bejövő activity `serviceUrl` mezőjét és frissítse az `APP_TEAMS_SERVICE_URL`-t |

### WhatsApp

| Probléma | Megoldás |
|----------|---------|
| Üzenet nem megy ki | Ellenőrizze a Twilio Console **Messaging Logs**-ot: https://console.twilio.com/us1/monitor/logs/sms |
| 21608 hiba (unverified number) | Sandbox módban a fogadó számnak csatlakoznia kell a sandbox-hoz (`join <code>`) |
| Webhook nem hívódik | Ellenőrizze a Sandbox settings webhook URL-jét; lokálisan az ngrok fut-e |
| `whatsapp_unauthorized` log | A küldő szám nincs az `APP_WHATSAPP_ALLOWED_NUMBERS` listában |
| 20003 hiba (auth) | Rossz `APP_WHATSAPP_ACCOUNT_SID` vagy `APP_WHATSAPP_AUTH_TOKEN` |

### Általános

| Probléma | Megoldás |
|----------|---------|
| Csatorna nem jelenik meg | Ellenőrizze, hogy `APP_<CHANNEL>_ENABLED=true` be van-e állítva a `.env`-ben |
| Nincs fallback a web UI-ra | Az `InteractionBroker` automatikusan küld a web_ui-nak is — ellenőrizze az SSE kapcsolatot |
| Pending interaction nem található | Lehet, hogy lejárt — ellenőrizze a `GET /api/interactions/pending` végpontot |

---

## 7. Biztonsági javaslatok

- **Teams:** Az Azure Bot Framework beépített token-validációt biztosít. Éles környezetben engedélyezze a **Bot Framework Authentication**-t.
- **WhatsApp:** Mindig állítsa be az `APP_WHATSAPP_ALLOWED_NUMBERS` szűrőt éles környezetben.
- **HTTPS:** Minden webhook endpoint-nak HTTPS-en kell futnia. Lokális fejlesztéshez az ngrok automatikusan biztosítja ezt.
- **Secret rotation:** Rendszeresen cserélje az Azure client secret-et és a Twilio auth token-t.
- **Env fájl:** A `.env` fájl soha ne kerüljön verziókezelésbe (legyen a `.gitignore`-ban).
