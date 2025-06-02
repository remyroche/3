// website/source/js/utils.js
// Provides utility functions, including runtime language management and dynamic data translation.

// --- Language Management ---
let currentLang = 'fr'; // Default language, will be updated on load.

/**
 * Sets the current language for the site.
 * This is typically called by a language switcher or on initial load.
 * @param {string} lang - The language code ('fr' or 'en').
 */
function setLanguage(lang) {
    if (['fr', 'en'].includes(lang)) {
        currentLang = lang;
        localStorage.setItem('preferredLang', lang);
        console.log(`Runtime language set to: ${currentLang}`);
    } else {
        console.warn(`Unsupported language: ${lang}. Defaulting to ${currentLang}.`);
    }
}

/**
 * Gets the preferred language from localStorage or browser settings.
 * This determines the initial language for runtime translations.
 * @returns {string} The language code ('fr' or 'en').
 */
function getInitialLanguage() {
    const storedLang = localStorage.getItem('preferredLang');
    if (storedLang && ['fr', 'en'].includes(storedLang)) {
        return storedLang;
    }
    // navigator.language can be 'fr-FR', 'en-US', etc. We only need the 'fr' or 'en' part.
    const browserLang = navigator.language.split('-')[0];
    if (['fr', 'en'].includes(browserLang)) {
        return browserLang;
    }
    return 'fr'; // Default to French if no preference found
}

// Initialize currentLang on script load for runtime purposes
currentLang = getInitialLanguage();
// Note: The <html lang="..."> attribute is set by build.js for SEO and initial state.
// This currentLang is for JS-driven dynamic content.

/**
 * Retrieves translated text for a given field from a dynamic data item object.
 * This is used for content that is NOT known at build time (e.g., product details from a JSON file or API).
 * Assumes the item object has sub-objects for each language, e.g., item.name.fr, item.name.en.
 * @param {object} item - The object containing translatable fields (e.g., a product from products_details.json).
 * @param {string} fieldKey - The key of the field to translate (e.g., 'name', 'description_short').
 * @returns {string} The translated text or a fallback string.
 */
function getTranslatedText(item, fieldKey) {
    if (!item || typeof item !== 'object') {
        // console.warn(`getTranslatedText: Invalid item provided for fieldKey '${fieldKey}'.`);
        return `[Invalid item for ${fieldKey}]`;
    }
    const field = item[fieldKey];
    if (field === undefined || field === null) {
        // console.warn(`getTranslatedText: FieldKey '${fieldKey}' not found in item:`, item);
        return `[${fieldKey} missing]`;
    }

    // Check if the field itself is an object with language keys (e.g., field.fr, field.en)
    if (typeof field === 'object' && field !== null) {
        if (field[currentLang]) {
            return field[currentLang];
        }
        // Fallback logic: try French, then English, then any available language, then a placeholder
        if (field['fr']) return field['fr'];
        if (field['en']) return field['en'];
        const availableLangs = Object.keys(field);
        if (availableLangs.length > 0) return field[availableLangs[0]]; // Return first available translation
        return `[${fieldKey} translation N/A for lang '${currentLang}']`;
    }
    
    // If the field is a direct string, return it (assuming it's either not translatable or already in the correct language)
    if (typeof field === 'string') {
        return field;
    }

    // console.warn(`getTranslatedText: Field '${fieldKey}' is not a string or a translatable object:`, field);
    return `[${fieldKey} not translatable string/object]`;
}

/**
 * Helper function to set language and reload the page.
 * To be used by language switcher buttons in the UI.
 * @param {string} lang - The language code ('fr' or 'en').
 */
function setLanguageAndReload(lang) {
    setLanguage(lang); // Sets currentLang and localStorage
    // The build process creates separate directories for each language (e.g., /fr/, /en/).
    // We need to navigate to the equivalent page in the other language's directory.
    
    const currentPath = window.location.pathname; // e.g., "/fr/nos-produits.html" or "/nos-produits.html" if at root of a lang
    const pathSegments = currentPath.split('/').filter(segment => segment !== ''); // Remove empty segments

    let newPath;

    // Check if the first segment is a known language code
    if (pathSegments.length > 0 && languages.includes(pathSegments[0])) {
        // Replace the existing language code with the new one
        // e.g., /fr/nos-produits.html -> /en/nos-produits.html
        pathSegments[0] = lang;
        newPath = '/' + pathSegments.join('/');
    } else {
        // If no language code in path (e.g. running from source, or unexpected structure),
        // prepend the new language code. This might need adjustment based on dev vs. prod server structure.
        // For a built site, URLs should ideally always be prefixed with language.
        newPath = '/' + lang + (currentPath.startsWith('/') ? currentPath : '/' + currentPath);
    }
    
    // Preserve query parameters
    const queryParams = window.location.search;
    window.location.href = newPath + queryParams;
}

// --- Data Fetching ---
/**
 * Fetches JSON data from a given path.
 * @param {string} jsonPath - The relative or absolute path to the JSON file.
 * @returns {Promise<object|null>} - A promise that resolves with the parsed JSON data or null on error.
 */
async function fetchData(jsonPath) {
    try {
        const response = await fetch(jsonPath);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status} for ${jsonPath}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Could not load data from ${jsonPath}:`, error);
        showGlobalMessage(`Error loading data: ${jsonPath.split('/').pop()}`, 'error'); // User-friendly error
        return null;
    }
}

// Make languages array available if needed by setLanguageAndReload or other parts
const languages = ['fr', 'en'];

// Expose functions to global scope if not using modules, or handle exports if using modules.
// For this project structure, they are typically used as global functions.
window.setLanguage = setLanguage;
window.getInitialLanguage = getInitialLanguage;
window.getTranslatedText = getTranslatedText;
window.setLanguageAndReload = setLanguageAndReload;
window.fetchData = fetchData;
