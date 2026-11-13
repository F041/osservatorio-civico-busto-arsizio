// Prove di firestore.rules sull'emulatore. Dalla cartella del repo:
//   firebase emulators:exec --only firestore --project demo-osservatorio "node tests/regole/regole.test.mjs firestore.rules"
// (serve Java nel PATH; le dipendenze si installano con npm install in tests/regole)
import { readFileSync } from 'node:fs';
import { initializeTestEnvironment, assertSucceeds, assertFails } from '@firebase/rules-unit-testing';
import { addDoc, collection, doc, getDoc, getDocs, updateDoc, deleteDoc, setDoc, serverTimestamp, Timestamp } from 'firebase/firestore';

const env = await initializeTestEnvironment({
  projectId: 'demo-osservatorio',
  firestore: { rules: readFileSync(process.argv[2] ?? 'firestore.rules', 'utf8'), host: '127.0.0.1', port: 8085 },
});
const db = env.unauthenticatedContext().firestore();
const col = collection(db, 'segnalazioni');
const today = new Date();
const midnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
const daysAgo = n => Timestamp.fromDate(new Date(midnight.getTime() - n * 864e5));
const valid = () => ({ categoria: 'furto', data: Timestamp.fromDate(midnight), fascia: 'sera', cella: 'r13c12',
  fattori: ['illuminazione', 'isolata'], denuncia: 'no', creato: serverTimestamp() });

let ok = true;
async function prova(name, promise) {
  try { await promise; console.log('PASS', name); } catch (err) { ok = false; console.log('FAIL', name, err.message); }
}

const creazioni = [
  ['valida (oggi)', true, valid()],
  ['valida (89 giorni fa, nessun fattore)', true, { ...valid(), data: daysAgo(89), fattori: [] }],
  ['campo extra testo', false, { ...valid(), testo: 'Mario Rossi' }],
  ['campo mancante', false, (({ denuncia, ...r }) => r)(valid())],
  ['categoria non prevista', false, { ...valid(), categoria: 'spaccio' }],
  ['vecchio campo zona', false, { ...(({ cella, ...r }) => r)(valid()), zona: 'sacconago' }],
  ['cella ai bordi (r33c24)', true, { ...valid(), cella: 'r33c24' }],
  ['cella ai bordi (r00c00)', true, { ...valid(), cella: 'r00c00' }],
  ['cella fuori griglia (riga 34)', false, { ...valid(), cella: 'r34c10' }],
  ['cella fuori griglia (colonna 25)', false, { ...valid(), cella: 'r10c25' }],
  ['cella con testo', false, { ...valid(), cella: 'r10c10 via Roma' }],
  ['cella numero', false, { ...valid(), cella: 1010 }],
  ['fascia non prevista', false, { ...valid(), fascia: '23:15' }],
  ['data futura', false, { ...valid(), data: daysAgo(-2) }],
  ['data oltre 91 giorni', false, { ...valid(), data: daysAgo(120) }],
  ['data come stringa', false, { ...valid(), data: '2026-10-01' }],
  ['fattori duplicati', false, { ...valid(), fattori: ['degrado', 'degrado'] }],
  ['fattore non previsto', false, { ...valid(), fattori: ['uomo alto con giacca rossa'] }],
  ['fattori non lista', false, { ...valid(), fattori: 'degrado' }],
  ['creato falsificato', false, { ...valid(), creato: Timestamp.now() }],
];
for (const [name, expected, data] of creazioni) {
  await prova(name, (expected ? assertSucceeds : assertFails)(addDoc(col, data)));
}

// Un documento già scritto (con le regole disattivate) per provare letture, modifiche e cancellazioni
await env.withSecurityRulesDisabled(ctx => setDoc(doc(ctx.firestore(), 'segnalazioni/esistente'), { ...valid(), creato: Timestamp.now() }));
const esistente = doc(db, 'segnalazioni/esistente');
await prova('lettura singola negata', assertFails(getDoc(esistente)));
await prova('lettura elenco negata', assertFails(getDocs(col)));
await prova('modifica negata', assertFails(updateDoc(esistente, { categoria: 'altro' })));
await prova('cancellazione negata', assertFails(deleteDoc(esistente)));
await prova('altra collezione negata', assertFails(addDoc(collection(db, 'altro'), valid())));

// Stesso id usato due volte (nuovo tentativo con la rete lenta, js/segnala.js): il secondo invio va rifiutato
await env.clearFirestore();
const ref = doc(col);
await prova('primo invio con id fisso', assertSucceeds(setDoc(ref, valid())));
await prova('secondo invio con lo stesso id rifiutato', assertFails(setDoc(ref, valid())));
let n = 0;
await env.withSecurityRulesDisabled(async ctx => { n = (await getDocs(collection(ctx.firestore(), 'segnalazioni'))).size; });
if (n === 1) console.log('PASS un solo documento'); else { ok = false; console.log('FAIL documenti:', n); }

await env.cleanup();
console.log(ok ? 'Tutte le prove superate' : 'Qualche prova è fallita');
process.exit(ok ? 0 : 1);
