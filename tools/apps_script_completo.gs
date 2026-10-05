/* =====================================================================
 * ARTE BIANCA — script del foglio (uno per sede)
 * - doGet  : pannello Gestione (JSONP con password) e disponibilità pubblica
 * - doPost : ordini, prenotazioni e Business Lunch inviati dal sito
 * ===================================================================== */

var PASSWORD = 'ArteBianca2026';

// Vuoto = verifica anti-robot lato foglio disattivata (accetta tutto).
// Il sito resta protetto da "Non sono un robot" e dal campo trappola.
var RECAPTCHA_SECRET = '';


/* ============ PANNELLO GESTIONE (GET) ============ */

function doGet(e) {
  var p = (e && e.parameter) || {};
  var cb = String(p.callback || '').replace(/[^\w$.]/g, '');
  var risposta;
  try {
    if (p.azione === 'esauritiPubblico') {
      // lettura pubblica per il sito: nessuna password
      risposta = { ok: true, dati: { esauriti: leggiEsauriti(SpreadsheetApp.getActiveSpreadsheet()) } };
    } else if (p.pw !== PASSWORD) {
      risposta = { ok: false, errore: 'password' };
    } else {
      risposta = { ok: true, dati: esegui(p) };
    }
  } catch (err) {
    risposta = { ok: false, errore: String(err) };
  }
  var testoRisposta = JSON.stringify(risposta);
  if (cb) {
    return ContentService.createTextOutput(cb + '(' + testoRisposta + ');')
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
  return ContentService.createTextOutput(testoRisposta).setMimeType(ContentService.MimeType.JSON);
}


/* ============ SITO -> FOGLIO (POST) ============ */

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    var dati = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    var f = SpreadsheetApp.getActiveSpreadsheet();
    if (dati.tipo === 'ordine') { scriviOrdine(f, dati); }
    if (dati.tipo === 'prenotazione' && verificaRecaptcha(dati.recaptcha)) { scriviPrenotazione(f, dati); }
    if (dati.tipo === 'catering') { scriviBusinessLunch(f, dati); }
    return ContentService.createTextOutput('ok');
  } catch (err) {
    return ContentService.createTextOutput('errore: ' + err);
  } finally {
    try { lock.releaseLock(); } catch (x) {}
  }
}

// true se la richiesta è genuina; con RECAPTCHA_SECRET vuoto passa sempre
function verificaRecaptcha(token) {
  if (!RECAPTCHA_SECRET) return true;
  if (!token) return false;
  try {
    var r = UrlFetchApp.fetch('https://www.google.com/recaptcha/api/siteverify', {
      method: 'post', payload: { secret: RECAPTCHA_SECRET, response: token }, muteHttpExceptions: true
    });
    return JSON.parse(r.getContentText()).success === true;
  } catch (e) {
    return false;
  }
}


/* ============ AZIONI DEL PANNELLO ============ */

function esegui(p) {
  var f = SpreadsheetApp.getActiveSpreadsheet();

  switch (p.azione) {

    case 'riepilogo':
      return {
        ordini: ultimeRighe(f, 'Ordini', 40),
        prenotazioni: ultimeRighe(f, 'Prenotazioni', 40),
        note: leggiNote(f),
        slotChiusi: leggiSlot(f),
        esauriti: leggiEsauriti(f)
      };

    case 'notaAggiungi':
      aggiungiNota(f, p.autore || '', p.testo || '');
      return { note: leggiNote(f) };

    case 'notaFatta':
      segnaNota(f, Number(p.riga));
      return { note: leggiNote(f) };

    case 'slotCambia':
      cambiaSlot(f, p.data, p.ora, p.chiuso === 'si');
      return { slotChiusi: leggiSlot(f) };

    case 'esauritoCambia':
      cambiaEsaurito(f, p.nome || '', p.esaurito === 'si');
      return { esauriti: leggiEsauriti(f) };

    case 'ordineAggiungi':
      scriviOrdine(f, {
        locale: '📞 Telefono',
        cliente: p.cliente || '', telefono: p.telefono || '',
        ritiro: p.ritiro || '', articoli: p.articoli || '',
        totale: Number(p.totale) || 0, note: p.note || ''
      });
      return { ordini: ultimeRighe(f, 'Ordini', 40) };

    case 'prenotazioneElimina':
      eliminaPrenotazione(f, Number(p.riga), p.cliente || '', p.data || '', p.ora || '');
      return { prenotazioni: ultimeRighe(f, 'Prenotazioni', 40) };

    case 'prenotazioneAggiungi':
      scriviPrenotazione(f, {
        locale: '📞 Telefono',
        cliente: p.cliente || '', telefono: p.telefono || '', email: p.email || '',
        data: p.data || '', ora: p.ora || '', persone: p.persone || ''
      });
      return { prenotazioni: ultimeRighe(f, 'Prenotazioni', 40) };

    default:
      throw 'azione sconosciuta';
  }
}


/* ============ SCRITTURA ============ */

// il "+" iniziale (es. +32 470...) altrimenti diventa una formula (#ERROR!)
function tel(v) {
  v = String(v || '');
  return v ? "'" + v : '';
}

function intestazione(s, colonne) {
  s.getRange(1, 1, 1, colonne).setFontWeight('bold');
  s.setFrozenRows(1);
}

function scriviOrdine(f, d) {
  var s = f.getSheetByName('Ordini');
  if (!s) {
    s = f.insertSheet('Ordini');
    s.appendRow(['Data e ora','Locale','Cliente','Telefono','Ritiro alle','Articoli','Totale','Note','Stato']);
    intestazione(s, 9);
  }
  s.appendRow([new Date(), d.locale||'', d.cliente||'', tel(d.telefono), d.ritiro||'',
               d.articoli||'', Number(d.totale)||0, d.note||'', '']);
  var riga = s.getLastRow();
  s.getRange(riga,1).setNumberFormat('dd/MM/yyyy HH:mm');
  s.getRange(riga,7).setNumberFormat('€ #,##0.00');
}

function scriviPrenotazione(f, d) {
  var s = f.getSheetByName('Prenotazioni');
  if (!s) {
    s = f.insertSheet('Prenotazioni');
    s.appendRow(['Ricevuta il','Locale','Cliente','Telefono','Email','Data','Ora','Persone','Stato']);
    intestazione(s, 9);
  }
  s.appendRow([new Date(), d.locale||'', d.cliente||'', tel(d.telefono), d.email||'',
               d.data||'', d.ora||'', d.persone||'', '']);
  s.getRange(s.getLastRow(),1).setNumberFormat('dd/MM/yyyy HH:mm');
}

function scriviBusinessLunch(f, d) {
  var s = f.getSheetByName('Business Lunch');
  if (!s) {
    s = f.insertSheet('Business Lunch');
    s.appendRow(['Ricevuta il','Azienda','Referente','Telefono','Email','Data','Fascia','Persone',
                 'Totale','P.IVA','Indirizzo','Note','Stato']);
    intestazione(s, 13);
  }
  s.appendRow([new Date(), d.azienda||'', d.referente||'', tel(d.telefono), d.email||'',
               d.data||'', d.fascia||'', d.persone||'', Number(d.totale)||0,
               d.piva||'', d.indirizzo||'', d.note||'', '']);
  var riga = s.getLastRow();
  s.getRange(riga, 1).setNumberFormat('dd/MM/yyyy HH:mm');
  s.getRange(riga, 9).setNumberFormat('€ #,##0.00');
}


/* ============ LETTURA ============ */

function ultimeRighe(f, nome, quante) {
  var s = f.getSheetByName(nome);
  if (!s || s.getLastRow() < 2) return { intestazioni: [], righe: [] };

  var totale = s.getLastRow() - 1;
  var da = Math.max(2, s.getLastRow() - quante + 1);
  var n = s.getLastRow() - da + 1;

  var intest = s.getRange(1, 1, 1, s.getLastColumn()).getDisplayValues()[0];
  var righe = s.getRange(da, 1, n, s.getLastColumn()).getDisplayValues();
  righe.reverse();

  // numero di riga nel foglio di ogni elemento (serve per eliminare)
  var numeri = [];
  for (var r = s.getLastRow(); r >= da; r--) numeri.push(r);

  return { intestazioni: intest, righe: righe, numeri: numeri, totale: totale, primaRiga: da };
}


/* ============ ELIMINA PRENOTAZIONE (cliente che disdice) ============ */

// Per sicurezza controlla che la riga sia ancora quella vista nel pannello
// (nome, data e ora uguali): se nel frattempo la lista è cambiata non tocca nulla.
function eliminaPrenotazione(f, riga, cliente, data, ora) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var s = f.getSheetByName('Prenotazioni');
    if (!s || !(riga >= 2) || riga > s.getLastRow()) throw 'Prenotazione non trovata: aggiorna la pagina.';
    var intest = s.getRange(1, 1, 1, s.getLastColumn()).getDisplayValues()[0];
    var v = s.getRange(riga, 1, 1, s.getLastColumn()).getDisplayValues()[0];
    var c = intest.indexOf('Cliente'), d = intest.indexOf('Data'), o = intest.indexOf('Ora');
    if (c < 0 || d < 0 || o < 0 || v[c] !== cliente || v[d] !== data || v[o] !== ora) {
      throw 'La lista è cambiata: aggiorna la pagina e riprova.';
    }
    s.deleteRow(riga);
  } finally {
    lock.releaseLock();
  }
}


/* ============ BACHECA NOTE ============ */

function foglioNote(f) {
  var s = f.getSheetByName('Bacheca');
  if (!s) {
    s = f.insertSheet('Bacheca');
    s.appendRow(['Data e ora', 'Autore', 'Messaggio', 'Fatto']);
    intestazione(s, 4);
  }
  return s;
}

function leggiNote(f) {
  var s = foglioNote(f);
  if (s.getLastRow() < 2) return [];
  var v = s.getRange(2, 1, s.getLastRow() - 1, 4).getDisplayValues();
  var out = [];
  for (var i = 0; i < v.length; i++) {
    out.push({ riga: i + 2, data: v[i][0], autore: v[i][1], testo: v[i][2], fatto: v[i][3] === 'x' });
  }
  out.reverse();
  return out;
}

function aggiungiNota(f, autore, testo) {
  var s = foglioNote(f);
  s.appendRow([new Date(), autore, testo, '']);
  s.getRange(s.getLastRow(), 1).setNumberFormat('dd/MM/yyyy HH:mm');
}

function segnaNota(f, riga) {
  var s = foglioNote(f);
  if (riga < 2 || riga > s.getLastRow()) return;
  var attuale = s.getRange(riga, 4).getDisplayValue();
  s.getRange(riga, 4).setValue(attuale === 'x' ? '' : 'x');
}


/* ============ SLOT CHIUSI ============ */

function foglioSlot(f) {
  var s = f.getSheetByName('SlotChiusi');
  if (!s) {
    s = f.insertSheet('SlotChiusi');
    s.appendRow(['Data', 'Ora', 'Chiuso']);
    intestazione(s, 3);
  }
  return s;
}

function leggiSlot(f) {
  var s = foglioSlot(f);
  if (s.getLastRow() < 2) return [];
  var v = s.getRange(2, 1, s.getLastRow() - 1, 3).getDisplayValues();
  var out = [];
  for (var i = 0; i < v.length; i++) {
    if (v[i][2] === 'x') out.push({ data: v[i][0], ora: v[i][1] });
  }
  return out;
}

function cambiaSlot(f, data, ora, chiuso) {
  var s = foglioSlot(f);
  var v = s.getLastRow() > 1 ? s.getRange(2, 1, s.getLastRow() - 1, 3).getDisplayValues() : [];
  for (var i = 0; i < v.length; i++) {
    if (v[i][0] === data && v[i][1] === ora) {
      s.getRange(i + 2, 3).setValue(chiuso ? 'x' : '');
      return;
    }
  }
  if (chiuso) s.appendRow([data, ora, 'x']);
}


/* ============ DISPONIBILITÀ PRODOTTI ============ */

function foglioEsauriti(f) {
  var s = f.getSheetByName('Esauriti');
  if (!s) {
    s = f.insertSheet('Esauriti');
    s.appendRow(['Prodotto', 'Segnato il']);
    intestazione(s, 2);
  }
  return s;
}

function leggiEsauriti(f) {
  var s = foglioEsauriti(f);
  if (s.getLastRow() < 2) return [];
  var v = s.getRange(2, 1, s.getLastRow() - 1, 1).getDisplayValues();
  var out = [];
  for (var i = 0; i < v.length; i++) {
    if (v[i][0]) out.push(v[i][0]);
  }
  return out;
}

function cambiaEsaurito(f, nome, esaurito) {
  if (!nome) return;
  var s = foglioEsauriti(f);
  var v = s.getLastRow() > 1 ? s.getRange(2, 1, s.getLastRow() - 1, 1).getDisplayValues() : [];
  for (var i = v.length - 1; i >= 0; i--) {
    if (v[i][0] === nome) {
      if (!esaurito) s.deleteRow(i + 2);
      return;
    }
  }
  if (esaurito) {
    s.appendRow([nome, new Date()]);
    s.getRange(s.getLastRow(), 2).setNumberFormat('dd/MM/yyyy HH:mm');
  }
}
