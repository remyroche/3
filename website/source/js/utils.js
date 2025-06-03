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
    setLanguage(lang); // Updates currentLang and localStorage

    try {
        const currentUrl = new URL(window.location.href);
        const newUrl = new URL(currentUrl); // Create a mutable copy

        let pathSegments = newUrl.pathname.split('/').filter(segment => segment !== '');
        
        // Remove existing language prefix if present
        if (pathSegments.length > 0 && (pathSegments[0] === 'fr' || pathSegments[0] === 'en')) {
            pathSegments.shift(); 
        }

        // Prepend the new language code
        newUrl.pathname = `/${lang}/${pathSegments.join('/')}`;

        // Ensure index.html for root paths of a language directory
        if (newUrl.pathname === `/${lang}/` || newUrl.pathname === `/${lang}`) {
            newUrl.pathname = `/${lang}/index.html`;
        }
        // Ensure path doesn't end with just / if it's not the root of the language
        if (newUrl.pathname.endsWith('/') && newUrl.pathname !== `/${lang}/`) {
            newUrl.pathname = newUrl.pathname.slice(0, -1);
        }
        
        window.location.href = newUrl.href; // newUrl.href includes existing query parameters

    } catch (error) {
        console.error("Error constructing new language URL:", error);
        // Fallback to simpler, potentially less robust mechanism if URL parsing fails
        const currentPath = window.location.pathname;
        const queryParams = window.location.search;
        let pageName = currentPath.split('/').pop() || "index.html";
        if (pageName === 'fr' || pageName === 'en') pageName = "index.html"; // Basic check for lang code as page name
        window.location.href = `/${lang}/${pageName}${queryParams}`;
    }
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
