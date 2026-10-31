// Voci del modulo di segnalazione e loro etichette.
// I codici (id) devono coincidere con quelli ammessi in firestore.rules e in scripts/build_sicurezza.py.

export const FIREBASE_CONFIG = {
    apiKey: 'AIzaSyDrun_yWQwO4mDIhA48pLAMI0OKF2MRRiQ',
    authDomain: 'osservatorio-civico-busto.firebaseapp.com',
    projectId: 'osservatorio-civico-busto',
    appId: '1:482984183218:web:c84a68a802a822454a50ab',
};

// Chiave del sito Fraud Defense (reCAPTCHA Enterprise, a punteggio) per App Check: pubblica per natura.
// Registrata nel progetto osservatorio-civico-busto per il solo dominio f041.github.io.
export const RECAPTCHA_SITE_KEY = '6LfDHwouAAAAADDVYFZFnNqE9XzHSNNEbhapTJum';

export const GIORNI_INDIETRO = 90;

export const CATEGORIE = [
    { id: 'insicurezza', label: 'Sensazione di insicurezza', desc: 'Nessun episodio preciso, ma non mi sentivo al sicuro' },
    { id: 'furto', label: 'Furto o tentato furto', desc: 'Borseggio, bici, auto, casa, negozio' },
    { id: 'molestia', label: 'Molestia', desc: 'Commenti, insulti, pedinamento, contatti indesiderati' },
    { id: 'aggressione', label: 'Aggressione o minaccia', desc: 'Violenza fisica o minacce' },
    { id: 'vandalismo', label: 'Vandalismo o degrado', desc: 'Danni, rifiuti abbandonati, luoghi trascurati' },
    { id: 'altro', label: 'Altro', desc: '' },
];

export const FASCE = [
    { id: 'mattina', label: 'Mattina', desc: '6–12' },
    { id: 'pomeriggio', label: 'Pomeriggio', desc: '12–18' },
    { id: 'sera', label: 'Sera', desc: '18–22' },
    { id: 'notte', label: 'Notte', desc: '22–6' },
];

export const FATTORI = [
    { id: 'illuminazione', label: 'Poca illuminazione' },
    { id: 'isolata', label: 'Zona isolata o poco frequentata' },
    { id: 'persone-moleste', label: 'Persone moleste o aggressive' },
    { id: 'degrado', label: 'Degrado o sporcizia' },
    { id: 'trasporti', label: 'Fermata, stazione o parcheggio' },
    { id: 'nessuno-intorno', label: 'Nessuno a cui chiedere aiuto' },
];

export const DENUNCIA = [
    { id: 'si', label: 'Sì' },
    { id: 'no', label: 'No' },
    { id: 'non-dico', label: 'Preferisco non dirlo' },
];
