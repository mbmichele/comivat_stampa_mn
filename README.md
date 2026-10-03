# comunicaz_prov_mn

Feed RSS non ufficiale che aggrega tre fonti pubbliche della Provincia di
Mantova:

| Fonte | Pagina | Come viene letta |
|---|---|---|
| Comunicati stampa | [cs_home.jsp](https://www.provincia.mantova.it/cs_home.jsp?ID_LINK=64&area=24) | scraping (nessun feed nativo) |
| Eventi | [events.jsp](https://www.provincia.mantova.it/events.jsp?ID_LINK=3&area=5) | scraping (nessun feed nativo) |
| Notizie | [news.jsp](https://www.provincia.mantova.it/news.jsp?areaNews=11) | il sito offre già un feed nativo ([news_rss.jsp](https://www.provincia.mantova.it/rss/news_rss.jsp?areaNews=11)), letto direttamente |

Gli elementi delle tre fonti vengono uniti in un unico `feed.xml`, ordinati
per data decrescente e troncati a un massimo di 60 elementi totali (soglia
configurabile con `MAX_ITEMS` in `scripts/generate_feed.py`).

Ogni elemento del feed contiene: **titolo**, **data**, **descrizione**
(quando presente) e **link** alla pagina originale.

## Come funziona

1. `scripts/generate_feed.py` raccoglie le tre fonti:
   - **comunicati stampa**: scarica la pagina dell'archivio, individua ogni
     comunicato (tramite i link `cs_context.jsp?...id_context=...`), risale
     al blocco di testo che lo contiene e ne estrae data, titolo, link e
     descrizione (le etichette di categoria come "per il cittadino," / "per
     enti ed imprese," vengono scartate perché terminano sempre con una
     virgola);
   - **eventi**: scarica la pagina del calendario, individua ogni evento
     (tramite i link `events_detail.jsp?...ID_EVENT=...`), estrae la data di
     inizio (usata come data dell'elemento RSS), l'eventuale data di fine
     (riportata in descrizione come "Fino al ...") e le righe restanti
     (categoria, luogo/orario) come descrizione;
   - **notizie**: legge direttamente il feed RSS nativo del sito
     (`/rss/news_rss.jsp?areaNews=11`), senza bisogno di scraping.

   Se una fonte fallisce (es. il sito è temporaneamente irraggiungibile),
   le altre due vengono comunque pubblicate: l'errore è loggato ma non
   blocca l'intera generazione.
2. Lo script unisce, ordina e tronca gli elementi, poi scrive
   `docs/feed.xml` (RSS 2.0).
3. GitHub Pages pubblica il contenuto della cartella `docs/`.
4. La GitHub Action `.github/workflows/generate-feed.yml` rigenera il feed e
   fa il commit solo se cambia qualcosa. È attivabile in due modi
   indipendenti e ridondanti tra loro, entrambi orari:
   - **interno**: uno `schedule` nativo di GitHub Actions (`cron: "0 * * * *"`
     nel file del workflow);
   - **esterno**: un cronjob su cron-job.org che chiama l'API di GitHub.

   Avere entrambi garantisce che, se uno dei due meccanismi salta
   un'esecuzione (es. ritardi tipici degli schedule di GitHub Actions sui
   runner condivisi, o un disservizio del cron esterno), l'altro copra
   comunque l'aggiornamento orario del feed.

   Poiché i due trigger possono scattare quasi nello stesso istante, il
   workflow è protetto su due livelli: `concurrency` mette in coda le
   esecuzioni invece di farle correre in parallelo, e lo step di commit/push
   riprova automaticamente (con `git fetch` + `rebase`) se un push viene
   rifiutato perché un'altra esecuzione ha già aggiornato il branch nel
   frattempo.

## Guida completa all'implementazione

### 1. Caricare il codice nel repository

Il repository [mbmichele/comunicaz_prov_mn](https://github.com/mbmichele/comunicaz_prov_mn)
è già stato creato. Per aggiornarlo con questo pacchetto:

```bash
cd comunicaz_prov_mn
git init
git remote add origin https://github.com/mbmichele/comunicaz_prov_mn.git
git add -A
git commit -m "Aggiornamento pacchetto"
git branch -M main
git push -u origin main
```

(in alternativa puoi trascinare i file dall'interfaccia web di GitHub,
con "Add file → Upload files").

### 2. Rendere pubblico l'accesso HTTP al feed (GitHub Pages)

1. Nel repository vai su **Settings → Pages** (menu a sinistra).
2. Alla voce "Build and deployment" → "Source" scegli **Deploy from a
   branch**.
3. In "Branch" seleziona `main` e come cartella `/docs`, poi **Save**.
4. Dopo qualche minuto GitHub mostrerà in cima alla pagina l'URL pubblico,
   del tipo:

   ```
   https://mbmichele.github.io/comunicaz_prov_mn/
   ```

5. Il feed RSS sarà raggiungibile via HTTP (accesso pubblico, nessun
   login richiesto) all'indirizzo:

   ```
   https://mbmichele.github.io/comunicaz_prov_mn/feed.xml
   ```

   Questo è l'URL da inserire in un lettore RSS o da collegare al sito del
   Comune/progetto.

6. Verifica subito che il feed esista già lanciando il workflow a mano
   (vedi punto 5 più sotto), altrimenti GitHub Pages pubblicherà solo
   `index.html` finché `feed.xml` non viene generato la prima volta.

### 3. Creare il Personal Access Token per innescare la Action da fuori

Il cronjob esterno deve poter chiamare l'API di GitHub per lanciare il
workflow: serve quindi un token.

1. Vai su **github.com → foto profilo (in alto a destra) → Settings**.
2. Nel menu a sinistra, in fondo, **Developer settings**.
3. **Personal access tokens → Fine-grained tokens → Generate new token**.
4. Compila:
   - **Token name**: es. `cron-comunicaz-prov-mn`
   - **Expiration**: scegli una durata (es. 1 anno; alla scadenza andrà
     rigenerato e sostituito nel cronjob).
   - **Repository access**: "Only select repositories" → seleziona
     `comunicaz_prov_mn`.
   - **Permissions → Repository permissions → Actions**: imposta
     **Read and write**.
5. Genera il token e **copialo subito** (GitHub lo mostra una sola volta):
   inizia con `github_pat_...`.

### 4. Configurare il cronjob esterno su cron-job.org

Il cron interno (`schedule` nel workflow) è già configurato e attivo di
default appena il file è su `main` — non richiede setup. Questo passaggio
aggiunge il secondo livello, esterno, come richiesto per ridondanza.

1. Vai su [cron-job.org](https://cron-job.org) e crea un account gratuito
   (o accedi se ne hai già uno, come per `ameteorss`).
2. Nel pannello, clicca **Create cronjob**.
3. Compila i campi principali:
   - **Title**: es. `comunicaz_prov_mn - genera feed`
   - **URL**:
     ```
     https://api.github.com/repos/mbmichele/comunicaz_prov_mn/actions/workflows/generate-feed.yml/dispatches
     ```
4. Apri la sezione **Advanced** (o "Extended data") e imposta:
   - **Request method**: `POST`
   - **Request body / Save responses → Body**:
     ```json
     {"ref": "main"}
     ```
   - **Headers** (aggiungi tre header):
     ```
     Content-Type: application/json
     Accept: application/vnd.github+json
     Authorization: Bearer <IL_TUO_PERSONAL_ACCESS_TOKEN>
     ```
5. Nella sezione **Schedule**, imposta l'esecuzione **ogni ora** (es.
   "every hour" oppure minuto `0` di ogni ora).
6. Salva il cronjob con **Create**.
7. Usa il tasto **Test run** (o "Run now") offerto da cron-job.org per
   verificare subito che la chiamata funzioni: una risposta HTTP `204 No
   Content` indica che GitHub ha accettato la richiesta e ha avviato il
   workflow.
8. Vai nel repository GitHub, tab **Actions**: dovresti vedere
   l'esecuzione di "Genera feed RSS" partita e, a fine corsa, un eventuale
   commit automatico "Aggiorna feed.xml" se il contenuto era cambiato.

### 5. Prima generazione manuale (opzionale ma consigliata)

Prima di aspettare il cronjob, genera subito il feed una volta a mano:

1. Nel repository vai su **Actions → Genera feed RSS**.
2. Clicca **Run workflow** (branch `main`) → **Run workflow**.
3. Attendi il completamento (icona verde) e verifica che
   `https://mbmichele.github.io/comunicaz_prov_mn/feed.xml` risponda con il
   feed aggiornato.

### Riepilogo URL utili

Repository:

```
https://github.com/mbmichele/comunicaz_prov_mn
```

Feed RSS pubblico:

```
https://mbmichele.github.io/comunicaz_prov_mn/feed.xml
```

Pagina informativa (GitHub Pages):

```
https://mbmichele.github.io/comunicaz_prov_mn/
```

Endpoint per il cronjob esterno (POST, vedi sezione 4):

```
https://api.github.com/repos/mbmichele/comunicaz_prov_mn/actions/workflows/generate-feed.yml/dispatches
```

Feed RSS nativo delle notizie (fonte 3, usato internamente dallo script):

```
https://www.provincia.mantova.it/rss/news_rss.jsp?areaNews=11
```

## Sviluppo locale

```bash
pip install -r requirements.txt
python scripts/generate_feed.py
```

## Prompt per rigenerare questo pacchetto con un'AI

Se vuoi ricreare da zero questo progetto (o adattarlo a un'altra pagina di
comunicati stampa) con un assistente AI, puoi usare questo prompt:

```
Voglio un repository GitHub che generi un UNICO feed RSS pubblico non
ufficiale che aggrega tre fonti della Provincia di Mantova:

1. Comunicati stampa:
   https://www.provincia.mantova.it/cs_home.jsp?ID_LINK=64&area=24
   (nessun feed nativo: scraping)

   Esempio di un elemento della pagina:
   Titolo -> SETTIMANA CORTA, INCONTRO TR A IL PRESIDENTE DELLA PROVINCIA E LA CONSULTA
   Data item -> 07.09.2026 17:51
   tralascia -> per il cittadino, per enti ed imprese,
   descrizione -> Il problema restano i trasporti

2. Eventi:
   https://www.provincia.mantova.it/events.jsp?ID_LINK=3&area=5
   (nessun feed nativo: scraping; ogni evento ha una data di inizio,
   opzionalmente una data di fine, una categoria e un luogo/orario)

3. Notizie:
   https://www.provincia.mantova.it/news.jsp?areaNews=11
   (verifica prima se il sito offre già un proprio feed RSS nativo per
   questa sezione — in tal caso leggi direttamente quello invece di fare
   scraping della pagina HTML)

Il flusso RSS finale deve contenere titolo, data, descrizione e link per
ogni elemento, unendo le tre fonti, ordinate per data decrescente e
troncate a un numero massimo configurabile di elementi totali.

Requisiti:
- Script Python (requests + BeautifulSoup) con una funzione di raccolta
  per ciascuna fonte. Per le fonti da scrapare, individua ogni elemento
  tramite i link che puntano al dettaglio, risale al blocco di testo che
  lo contiene ed estrae titolo, data, link e descrizione, scartando
  automaticamente le etichette di categoria che terminano con una virgola
  (es. "per il cittadino,"). Se una fonte fallisce, le altre devono essere
  comunque pubblicate (l'errore va loggato, non deve bloccare le altre).
- Genera un file docs/feed.xml (RSS 2.0 valido, con guid, pubDate in
  formato RFC 822, fuso orario Europe/Rome).
- GitHub Action con doppia attivazione oraria, sia interna che esterna:
  uno "schedule" nativo di GitHub Actions (cron "0 * * * *") E un
  workflow_dispatch innescabile da un cronjob esterno (es. cron-job.org)
  che chiama l'API di GitHub; le due attivazioni sono ridondanti tra loro.
  Il workflow rigenera il feed e fa commit/push solo se il contenuto
  cambia, con gestione dei push concorrenti (fetch + rebase + retry) nel
  caso i due trigger scattino quasi insieme.
- docs/index.html minimale con link al feed, per la pubblicazione tramite
  GitHub Pages (branch main, cartella /docs).
- README con istruzioni di setup (creazione repo, GitHub Pages, PAT e
  configurazione del cronjob esterno) e con questo stesso prompt incluso,
  per poter rigenerare il pacchetto in futuro.
- Consegna il tutto come pacchetto .zip scaricabile, con un numero di
  versione nel nome del file (senza data).
```

