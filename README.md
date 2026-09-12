# comivat_stampa_mn

Feed RSS non ufficiale dei comunicati stampa della Provincia di Mantova,
generato via scraping dell'[archivio comunicati stampa](https://www.provincia.mantova.it/cs_home.jsp?ID_LINK=64&area=24)
(il sito non offre un proprio feed).

Ogni elemento del feed contiene: **titolo**, **data/ora di pubblicazione**,
**descrizione** (quando presente) e **link** al comunicato originale.

## Come funziona

1. `scripts/generate_feed.py` scarica la pagina dell'archivio, individua ogni
   comunicato (tramite i link `cs_context.jsp?...id_context=...`), risale al
   blocco di testo che lo contiene e ne estrae data, titolo, link e
   descrizione (le etichette di categoria come "per il cittadino," / "per
   enti ed imprese," vengono scartate perché terminano sempre con una
   virgola).
2. Lo script scrive `docs/feed.xml` (RSS 2.0).
3. GitHub Pages pubblica il contenuto della cartella `docs/`.
4. La GitHub Action `.github/workflows/generate-feed.yml` rigenera il feed e
   fa il commit solo se cambia qualcosa.

## Guida completa all'implementazione

### 1. Creare il repository e caricare il codice

1. Su GitHub crea un nuovo repository pubblico chiamato `comivat_stampa_mn`
   (se non esiste già). Deve essere **pubblico**, altrimenti GitHub Pages
   gratuito non pubblica il sito.
2. Estrai lo zip di questo pacchetto e carica tutto il contenuto sul
   branch `main`, ad esempio da terminale:

   ```bash
   cd comivat_stampa_mn
   git init
   git remote add origin https://github.com/<utente>/comivat_stampa_mn.git
   git add -A
   git commit -m "Setup iniziale"
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
   https://<utente>.github.io/comivat_stampa_mn/
   ```

5. Il feed RSS sarà raggiungibile via HTTP (accesso pubblico, nessun
   login richiesto) all'indirizzo:

   ```
   https://<utente>.github.io/comivat_stampa_mn/feed.xml
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
   - **Token name**: es. `cron-comivat-stampa-mn`
   - **Expiration**: scegli una durata (es. 1 anno; alla scadenza andrà
     rigenerato e sostituito nel cronjob).
   - **Repository access**: "Only select repositories" → seleziona
     `comivat_stampa_mn`.
   - **Permissions → Repository permissions → Actions**: imposta
     **Read and write**.
5. Genera il token e **copialo subito** (GitHub lo mostra una sola volta):
   inizia con `github_pat_...`.

### 4. Configurare il cronjob esterno su cron-job.org

1. Vai su [cron-job.org](https://cron-job.org) e crea un account gratuito
   (o accedi se ne hai già uno, come per `ameteorss`).
2. Nel pannello, clicca **Create cronjob**.
3. Compila i campi principali:
   - **Title**: es. `comivat_stampa_mn - genera feed`
   - **URL**:
     ```
     https://api.github.com/repos/<utente>/comivat_stampa_mn/actions/workflows/generate-feed.yml/dispatches
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
   `https://<utente>.github.io/comivat_stampa_mn/feed.xml` risponda con il
   feed aggiornato.

### Riepilogo URL utili

| Cosa | URL |
|---|---|
| Feed RSS pubblico | `https://<utente>.github.io/comivat_stampa_mn/feed.xml` |
| Pagina informativa | `https://<utente>.github.io/comivat_stampa_mn/` |
| Endpoint per il cronjob | `https://api.github.com/repos/<utente>/comivat_stampa_mn/actions/workflows/generate-feed.yml/dispatches` |

## Sviluppo locale

```bash
pip install -r requirements.txt
python scripts/generate_feed.py
```

## Prompt per rigenerare questo pacchetto con un'AI

Se vuoi ricreare da zero questo progetto (o adattarlo a un'altra pagina di
comunicati stampa) con un assistente AI, puoi usare questo prompt:

```
Voglio un repository GitHub che generi un feed RSS pubblico non ufficiale
a partire dagli elementi pubblicati alla pagina:
https://www.provincia.mantova.it/cs_home.jsp?ID_LINK=64&area=24

Il flusso RSS deve contenere titolo, data, descrizione e link di ogni
comunicato. Esempio di un elemento della pagina:

Titolo -> SETTIMANA CORTA, INCONTRO TR A IL PRESIDENTE DELLA PROVINCIA E LA CONSULTA
Data item -> 07.09.2026 17:51
tralascia -> per il cittadino, per enti ed imprese,
descrizione -> Il problema restano i trasporti

Requisiti:
- Script Python (requests + BeautifulSoup) che fa scraping della pagina,
  individua ogni comunicato tramite i link che puntano al dettaglio
  (pattern "cs_context.jsp?...id_context=..."), risale al blocco di testo
  che lo contiene ed estrae titolo, data, link e descrizione. Le etichette
  di categoria (che terminano sempre con una virgola, es. "per il
  cittadino,") vanno scartate automaticamente, indipendentemente da quante
  e quali sono.
- Genera un file docs/feed.xml (RSS 2.0 valido, con guid, pubDate in
  formato RFC 822, fuso orario Europe/Rome).
- GitHub Action con solo "workflow_dispatch" (nessuno schedule interno):
  deve essere innescabile da un cronjob esterno (es. cron-job.org) che
  chiama l'API di GitHub per lanciare il workflow ogni ora; il workflow
  rigenera il feed e fa commit/push solo se il contenuto cambia.
- docs/index.html minimale con link al feed, per la pubblicazione tramite
  GitHub Pages (branch main, cartella /docs).
- README con istruzioni di setup (creazione repo, GitHub Pages, PAT e
  configurazione del cronjob esterno) e con questo stesso prompt incluso,
  per poter rigenerare il pacchetto in futuro.
- Consegna il tutto come pacchetto .zip scaricabile, con un numero di
  versione nel nome del file.
```

