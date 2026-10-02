/* =====================================================================
 * RICEZIONE DAL SITO artebianca.be
 * Prenotazioni, ordini d'asporto e richieste Business Lunch inviate
 * dai moduli del sito arrivano qui (POST) e vengono scritte nei fogli
 * di questo file: "Prenotazioni", "Ordini", "Business Lunch".
 *
 * Controllo anti-robot (facoltativo): in Impostazioni progetto →
 * Proprietà script aggiungi RECAPTCHA_SECRET con la SECRET KEY di
 * reCAPTCHA. Se la proprietà manca, il controllo viene saltato.
 * ===================================================================== */

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    var d = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    if (!verificaCaptchaSito(d.recaptcha)) return rispostaSito({ ok: false, errore: 'captcha' });

    var f = SpreadsheetApp.getActiveSpreadsheet();

    if (d.tipo === 'prenotazione') {
      scriviRigaSito(f, 'Prenotazioni',
        ['Ricevuta il', 'Locale', 'Cliente', 'Telefono', 'Email', 'Data', 'Ora', 'Persone', 'Stato'],
        [new Date(), testo(d.locale), testo(d.cliente), telefonoTesto(d.telefono), testo(d.email),
         testo(d.data), testo(d.ora), testo(d.persone), '']);

    } else if (d.tipo === 'ordine') {
      var s = scriviRigaSito(f, 'Ordini',
        ['Data e ora', 'Locale', 'Cliente', 'Telefono', 'Ritiro alle', 'Articoli', 'Totale', 'Note', 'Stato'],
        [new Date(), testo(d.locale), testo(d.cliente), telefonoTesto(d.telefono), testo(d.ritiro),
         testo(d.articoli), Number(d.totale) || 0, testo(d.note), '']);
      s.getRange(s.getLastRow(), 7).setNumberFormat('€ #,##0.00');

    } else if (d.tipo === 'catering') {
      var b = scriviRigaSito(f, 'Business Lunch',
        ['Ricevuta il', 'Azienda', 'Referente', 'Telefono', 'Email', 'Data', 'Fascia', 'Persone',
         'Menu Pizza', 'Menu Ristorante', 'Totale', 'P.IVA', 'Indirizzo', 'Note', 'Lingua', 'Stato'],
        [new Date(), testo(d.azienda), testo(d.referente), telefonoTesto(d.telefono), testo(d.email),
         testo(d.data), testo(d.fascia), testo(d.persone), testo(d.menuPizza), testo(d.menuRistorante),
         Number(d.totale) || 0, testo(d.piva), testo(d.indirizzo), testo(d.note), testo(d.lingua), '']);
      b.getRange(b.getLastRow(), 11).setNumberFormat('€ #,##0.00');

    } else {
      return rispostaSito({ ok: false, errore: 'tipo sconosciuto' });
    }
    return rispostaSito({ ok: true });

  } catch (err) {
    return rispostaSito({ ok: false, errore: String(err) });
  } finally {
    try { lock.releaseLock(); } catch (x) {}
  }
}

// Scrive una riga nel foglio indicato (lo crea con l'intestazione se manca)
function scriviRigaSito(f, nome, intestazioni, valori) {
  var s = f.getSheetByName(nome);
  if (!s) {
    s = f.insertSheet(nome);
    s.appendRow(intestazioni);
    s.getRange(1, 1, 1, intestazioni.length).setFontWeight('bold');
    s.setFrozenRows(1);
  }
  s.appendRow(valori);
  s.getRange(s.getLastRow(), 1).setNumberFormat('dd/MM/yyyy HH:mm');
  return s;
}

function testo(v) {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

// Il "+" iniziale (es. +32 470...) altrimenti diventa una formula e dà #ERROR!
function telefonoTesto(v) {
  var t = testo(v);
  return t ? "'" + t : '';
}

function verificaCaptchaSito(token) {
  var segreto = PropertiesService.getScriptProperties().getProperty('RECAPTCHA_SECRET');
  if (!segreto) return true;
  if (!token) return false;
  try {
    var r = UrlFetchApp.fetch('https://www.google.com/recaptcha/api/siteverify', {
      method: 'post', payload: { secret: segreto, response: token }, muteHttpExceptions: true
    });
    return JSON.parse(r.getContentText()).success === true;
  } catch (e) {
    return false;
  }
}

function rispostaSito(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
