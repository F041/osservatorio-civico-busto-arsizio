// Formati usati da più pagine del sito
export const integer = new Intl.NumberFormat('it-IT');
// '2026-11-27' (anche seguita dall'ora) -> '27/11/2026'
export const formatDate = iso => iso.slice(0, 10).split('-').reverse().join('/');
