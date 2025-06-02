// website/source/js/utils.js
// Provides utility functions, including runtime language management and dynamic data translation.

let currentLang = 'fr'; 

function setLanguage(lang) {
    if (['fr', 'en'].includes(lang)) {
        currentLang = lang;
        localStorage.setItem('preferredLang', lang);
        console.log(`Runtime language set to: ${currentLang}`); // Dev-facing
    } else {
        console.warn(`Unsupported language: ${lang}. Defaulting to ${currentLang}.`); // Dev-facing
    }
}

function getInitialLanguage() {
    const storedLang = localStorage.getItem('preferredLang');
    if (storedLang && ['fr', 'en'].includes(storedLang)) {
        return storedLang;
    }
    const browserLang = navigator.language.split('-')[0];
    if (['fr', 'en'].includes(browserLang)) {
        return browserLang;
    }
    return 'fr'; 
}

currentLang = getInitialLanguage();

function getTranslatedText(item, fieldKey) {
    if (!item || typeof item !== 'object') {
        return `[Invalid item for ${fieldKey}]`; // Dev-facing or placeholder
    }
    const field = item[fieldKey];
    if (field === undefined || field === null) {
        return `[${fieldKey} missing]`; // Dev-facing or placeholder
    }
    if (typeof field === 'object' && field !== null) {
        if (field[currentLang]) return field[currentLang];
        if (field['fr']) return field['fr'];
        if (field['en']) return field['en'];
        const availableLangs = Object.keys(field);
        if (availableLangs.length > 0) return field[availableLangs[0]];
        return `[${fieldKey} ${t('public.js.translation_na_for_lang_suffix')} '${currentLang}']`; // New key: public.js.translation_na_for_lang_suffix (e.g., "translation N/A for lang")
    }
    if (typeof field === 'string') return field;
    return `[${fieldKey} ${t('public.js.not_translatable_suffix')}]`; // New key: public.js.not_translatable_suffix (e.g., "not translatable string/object")
}

function setLanguageAndReload(lang) {
    setLanguage(lang); 
    const currentPath = window.location.pathname; 
    const pathSegments = currentPath.split('/').filter(segment => segment !== '');
    let pageName = pathSegments[pathSegments.length -1] || "index.html";
    if (languages.includes(pageName) && pathSegments.length > 0 && pathSegments[0] === pageName) { // handles case like /fr becoming /en when pageName is fr
        pageName = "index.html";
    }


    let newPath;
    const langPathRegex = /^\/(fr|en)(\/|$)/; // Matches /fr/ or /en or /fr or /en/

    if (langPathRegex.test(currentPath)) {
        newPath = currentPath.replace(langPathRegex, `/${lang}$2`);
    } else {
        // If no language code, prepend. This is a fallback.
        // Assumes currentPath could be like "/nos-produits.html"
        newPath = `/${lang}${currentPath.startsWith('/') ? '' : '/'}${currentPath.startsWith('/') ? currentPath.substring(1) : currentPath}`;
        if (newPath === `/${lang}/`) newPath = `/${lang}/index.html`; // Ensure index.html for root path of language
    }
    
    const queryParams = window.location.search;
    window.location.href = newPath + queryParams;
}

async function fetchData(jsonPath) {
    try {
        const response = await fetch(jsonPath);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status} for ${jsonPath}`); // Dev-facing
        }
        return await response.json();
    } catch (error) {
        console.error(`Could not load data from ${jsonPath}:`, error); // Dev-facing
        // The t() call for the error message shown to user
        showGlobalMessage(`${t('public.js.error_loading_data_prefix')} ${jsonPath.split('/').pop()}`, 'error'); // New key: public.js.error_loading_data_prefix (e.g., "Error loading data:")
        return null;
    }
}

const languages = ['fr', 'en']; // Used by setLanguageAndReload

window.setLanguage = setLanguage;
window.getInitialLanguage = getInitialLanguage;
window.getTranslatedText = getTranslatedText;
window.setLanguageAndReload = setLanguageAndReload;
window.fetchData = fetchData;
